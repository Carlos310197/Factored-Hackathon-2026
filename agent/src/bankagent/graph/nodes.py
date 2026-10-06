"""Graph nodes implementing the agent workflow.
Each node is a function that takes (state, config) and returns a partial state update.
Identity comes from config['configurable']['ctx'], verified on every turn.
"""
import hashlib
import json
import logging
from dataclasses import asdict, replace
from datetime import datetime, timezone
from typing import Any

from langchain_core.runnables import RunnableConfig
from langgraph.types import interrupt
from opentelemetry import trace

from bankagent.context import PermissionDenied, SessionContext
from bankagent.data.serving import ServingError
from bankagent.decisions.jev import ChoiceAnswer, JevError
from bankagent.decisions.routing import Counters, decide
from bankagent.decisions.understand import (
    build_understand_request,
    parse_understanding,
    select_candidates,
)
from bankagent.decisions.trace_payload import alias_view, confirmation_payload, thresholds_map
from bankagent.decisions.verify import build_verify_request, parse_verify
from bankagent.graph.deps import Deps
from bankagent.graph.state import AgentState
from bankagent.guards import unknown_ids
from bankagent.handoff.packet import build_packet
from bankagent.ids import new_id
from bankagent.llm.client import LLMError
from bankagent.llm.compose import compose, open_questions
from bankagent.llm.extract import extract
from bankagent.llm.templates import (
    INTENT_LABELS,
    REASON_LABELS,
    confirmation_summary,
    dispute_filed,
    fallback_reply,
    handoff_failed,
    handoff_notice,
    txn_option,
)
from bankagent.tools.read import NotDeclined, NotFound
from bankagent.tools.write import AlreadyDisputed, HandoffFailed, PolicyRejected, WriteFailed

logger = logging.getLogger(__name__)
tracer = trace.get_tracer("bankagent")

# Routes that should NOT reset intent/target/reason from the routing decision
CARRY_ROUTES = ("file_dispute", "confirm")


def _ctx(config: RunnableConfig) -> SessionContext:
    """Extract verified session context from config."""
    return config["configurable"]["ctx"]


def _answers(result) -> dict:
    """Convert Jev answers to decision record format."""
    return {
        q: ({"label": a.label, "probabilities": a.probabilities} if isinstance(a, ChoiceAnswer) else {"p": a.p})
        for q, a in result.answers.items()
    }


def _refs(receipts: list[dict]) -> list[str]:
    """Extract dispute_id and handoff_id from receipts for the reply."""
    out = []
    for r in receipts:
        data = r.get("data")
        if r["source"] == "disputes":
            if isinstance(data, list):
                out += [x.get("dispute_id") for x in data if isinstance(x, dict)]
            elif isinstance(data, dict):
                out.append(data.get("dispute_id"))
        elif r["source"] == "handoffs" and isinstance(data, dict):
            out.append(data.get("handoff_id"))
    return list(dict.fromkeys(x for x in out if x))



def _card_hash(txn: dict, reason: str | None) -> str:
    """Hash of the structured confirmation card (merchant, date, amount, currency, reason)."""
    card = json.dumps(confirmation_payload(txn, reason), sort_keys=True, default=str)
    return hashlib.sha256(card.encode()).hexdigest()

class Nodes:
    """Graph node implementations."""
    
    def __init__(self, deps: Deps):
        self.d = deps
    
    # ---- Helpers --------------------------------------------------------------------
    
    def _log(self, state: AgentState, config: RunnableConfig, node: str, kind: str,
             payload: dict, versions: dict | None = None, latency_ms: int | None = None) -> None:
        """Log a decision record (best-effort, never breaks the turn)."""
        ctx = _ctx(config)
        try:
            self.d.store.log.append(ctx.session_id, state["turn_id"], node, kind, payload, versions, latency_ms)
        except Exception:
            logger.exception("decision record write failed")
    
    def _as_of(self, state: AgentState):
        """Parse as_of date from state."""
        from datetime import date
        return date.fromisoformat(state["as_of"])
    
    def _over_budget(self, config: RunnableConfig) -> bool:
        """Check if turn budget is exhausted."""
        return self.d.clock() > config["configurable"].get("deadline", float("inf"))
    
    def _offer(self, state: AgentState) -> bool:
        """Check if goal offers human handoff."""
        return bool((state.get("goal") or {}).get("offer_human"))
    
    def _resolve(self, state, config, candidates: list[dict], ex) -> dict[str, float] | None:
        """Resolver scores as evidence for Jev (resolver spec 3.2). Any failure: no scores, Jev alone."""
        if self.d.resolver is None or self.d.understand_qs_scored is None or ex is None or not candidates:
            return None
        start = self.d.clock()
        try:
            s = self.d.resolver.score(candidates, ex.mentions)
        except Exception as e:  # the resolver never blocks a turn
            self._log(state, config, "understand", "error", {"role": "resolver", "error": str(e)})
            return None
        self._log(state, config, "understand", "model",
                  {"probs": s.probs, "p_none": s.p_none, "best_raw_fit": s.best_raw_fit,
                   "contributions": {k: [list(c) for c in v] for k, v in s.contributions.items()}},
                  {"resolver": s.version}, int((self.d.clock() - start) * 1000))
        return s.probs

    def _decision_refs(self, u, qs: str) -> list[dict]:
        """Build decision references for handoff packet."""
        if u is None:
            return []
        th = self.d.thresholds.version
        refs = [{"question": "intent", "value": u.intent.label, "p": u.intent.p,
                 "question_set": qs, "thresholds": th}]
        refs += [{"question": q, "value": p, "question_set": qs, "thresholds": th}
                 for q, p in u.nouls.items() if p >= 0.3]
        return refs
    
    def _already_disputed(self, state: AgentState, existing: dict) -> dict:
        """Handle case where transaction was already disputed."""
        row = {k: existing.get(k) for k in ("dispute_id", "transaction_id", "status", "route", "reason", "created_at")}
        rec = {"receipt_id": new_id("RCP"), "source": "disputes", "as_of": state["as_of"], "data": [row]}
        ids = state["allowed_ids"] + ([row["dispute_id"]] if row["dispute_id"] else [])
        return {
            "receipts": state["receipts"] + [rec],
            "allowed_ids": ids,
            "route": {"next": "reply"},
            "goal": {"kind": "answer", "note": "already_disputed", "offer_human": self._offer(state)}
        }
    
    # ---- Nodes ----------------------------------------------------------------------
    
    def load_context(self, state: AgentState, config: RunnableConfig) -> dict:
        """Load customer data from serving. Keep the run_id from previous turns."""
        with tracer.start_as_current_span("load_context"):
            ctx = _ctx(config)
            base = {
                "receipts": [],
                "actions": [],
                "policy_checks": [],
                "decisions": [],
                "reasons": [],
                "goal": {},
                "reply": {},
                "escalated": False,
                "language": state.get("language") or ctx.lang,
                "counters": state.get("counters") or asdict(Counters()),
                "awaiting": state.get("awaiting") or "none",
                "queue": state.get("queue") or [],
                "pending": state.get("pending") or {},
                "allowed_ids": state.get("allowed_ids") or []
            }
            
            error = None
            for _ in range(2):  # One retry
                try:
                    if state.get("run_id"):
                        # Keep the run_id from previous turns
                        run_id, as_of = state["run_id"], state["as_of"]
                    else:
                        pointer = self.d.read.serving.pointer()
                        run_id, as_of = pointer.run_id, pointer.max_process_date
                    txns = self.d.read.list_transactions(ctx, run_id, self._as_of({"as_of": str(as_of)}))
                    break
                except ServingError as e:
                    error = e
            else:
                self._log(state, config, "load_context", "error", {"error": str(error)})
                return {
                    **base,
                    "goal": {"kind": "data_unavailable", "offer_human": True},
                    "reasons": ["data_unavailable"],
                    "route": {"next": "reply"}
                }
            
            self._log(state, config, "load_context", "tool", {
                "source": txns.source,
                "rows": len(txns.data),
                "run_id": run_id
            })
            
            allowed = sorted(set(base["allowed_ids"]) | {x["transaction_id"] for x in txns.data})
            
            return {
                **base,
                "run_id": run_id,
                "as_of": str(as_of),
                "candidates": txns.data,
                "allowed_ids": allowed,
                "route": {"next": "understand"}
            }
    
    def understand(self, state: AgentState, config: RunnableConfig) -> dict:
        """Extract facts and classify intent with Jev."""
        with tracer.start_as_current_span("understand"):
            ctx, msg, ex = _ctx(config), state["message"], None
            
            # The card's button sends confirm:<card_hash>: code checks equality, so no model reads the "yes".
            if state["awaiting"] == "confirmation" and msg.startswith("confirm:"):
                matched = bool(state.get("card_hash")) and msg == f"confirm:{state['card_hash']}"
                self._log(state, config, "understand", "guard", {"check": "confirm_token", "matched": matched})
                # A stale or forged token files nothing: show the current card again.
                return {"route": {"next": "file_dispute" if matched else "confirm"}, "awaiting": "none",
                        "reasons": [], "goal": {}, "queued_offer": None, "pending": {}}
            
            # Extract
            try:
                ex, call = extract(self.d.llm_client, self.d.models["extract"], msg, state["as_of"],
                                  state.get("recent") or [])
                self._log(state, config, "understand", "llm",
                         {"role": "extract", "output": asdict(ex), "usage": call.usage},
                         {"model": call.model, "prompt": call.prompt_version}, call.latency_ms)
            except LLMError as e:
                self._log(state, config, "understand", "error", {"role": "extract", "error": str(e)})
            
            # Determine language
            language = ex.language_detected if ex and ex.language_detected in ("es", "pt") else ctx.lang
            
            # Handle multi-intent
            queue = list(state.get("queue") or [])
            if ex and ex.multi_intent and ex.secondary_request_en:
                queue.append(ex.secondary_request_en)
            
            # Build Jev state
            facts = {
                "awaiting": state["awaiting"],
                "clarification": state.get("clarification"),
                "pending_request": state.get("pending") or None,
                "offered_queued_request": state.get("queued_offer"),
                "recent_exchanges": (state.get("recent") or [])[-2:],
                "reply_language": language
            }
            
            candidates = select_candidates(state["candidates"], ex.mentions if ex else None)
            scores = self._resolve(state, config, candidates, ex)
            qs = self.d.understand_qs_scored if scores is not None else self.d.understand_qs
            jev_state, questions, aliases = build_understand_request(
                qs,
                message=msg,
                gloss=ex.english_gloss if ex else None,
                gloss_mode=self.d.gloss_mode.get(language, "original_plus_gloss"),
                session_facts=facts,
                candidates=candidates,
                awaiting_confirmation=state["awaiting"] == "confirmation",
                confirmation_summary=state.get("confirmation_summary"),
                scores=scores
            )
            
            # Jev understand
            u = None
            try:
                res = self.d.jev.decide(jev_state, questions)
                u = parse_understanding(res, aliases)
                self._log(state, config, "understand", "jev",
                         {"answers": _answers(res), "usage": res.usage, "state_hash": res.state_hash,
                          "thresholds": thresholds_map(self.d.thresholds),
                          "aliases": alias_view(aliases, candidates)},
                         {"question_set": qs["version"],
                          "thresholds": self.d.thresholds.version, "model": res.model},
                         res.latency_ms)
            except JevError as e:
                self._log(state, config, "understand", "error", {"role": "jev", "error": str(e)})
            
            # Route
            route = decide(u, self.d.thresholds, state["awaiting"],
                          Counters(**state["counters"]), state.get("pending") or {})
            
            self._log(state, config, "understand", "route",
                     {"next": route.next, "reasons": list(route.reasons), "goal": route.goal})
            
            goal = dict(route.goal)
            if route.offer_human:
                goal["offer_human"] = True
            
            out = {
                "extraction": asdict(ex) if ex else None,
                "language": language,
                "queue": queue,
                "queued_offer": None,
                "route": {"next": route.next},
                "counters": asdict(route.counters),
                "reasons": list(route.reasons),
                "goal": goal,
                "awaiting": "none",
                "decisions": self._decision_refs(u, qs["version"]),
                "pending": ({"intent": route.intent, "target_txn_id": route.target_txn_id,
                            "dispute_reason": route.dispute_reason} if route.next == "clarify" else {})
            }
            
            if route.next not in CARRY_ROUTES:
                out.update({
                    "intent": route.intent,
                    "target_txn_id": route.target_txn_id,
                    "dispute_reason": route.dispute_reason,
                    "escalated": route.escalated
                })
            
            return out
    
    def answer_inquiry(self, state: AgentState, config: RunnableConfig) -> dict:
        """Answer account/transaction/dispute inquiries."""
        with tracer.start_as_current_span("answer_inquiry"):
            ctx, run_id, as_of, intent = _ctx(config), state["run_id"], self._as_of(state), state["intent"]
            note = None
            
            try:
                if intent == "account_info":
                    results = [self.d.read.get_accounts(ctx, run_id, as_of)]
                elif intent == "transaction_status":
                    results = [self.d.read.get_transaction(ctx, run_id, as_of, state["target_txn_id"])]
                elif intent == "decline_explanation":
                    try:
                        results = [self.d.read.explain_decline(ctx, run_id, as_of, state["target_txn_id"])]
                    except NotDeclined:
                        results = [self.d.read.get_transaction(ctx, run_id, as_of, state["target_txn_id"])]
                        note = "not_declined"
                else:  # dispute_status
                    results = [
                        self.d.write.list_disputes(ctx, as_of),
                        self.d.read.list_complaints(ctx, run_id, as_of)
                    ]
            except NotFound:
                return {"goal": {"kind": "ask_clarification", "topic": "transaction", "options": []},
                        "route": {"next": "clarify"}}
            except PermissionDenied:
                return {"goal": {"kind": "abstain", "offer_human": True}, "route": {"next": "reply"}}
            except ServingError:
                return {"goal": {"kind": "data_unavailable", "offer_human": True}, "route": {"next": "reply"}}
            
            ids = list(state["allowed_ids"])
            for r in results:
                self._log(state, config, "answer_inquiry", "tool",
                         {"source": r.source, "receipt_id": r.receipt_id})
                if isinstance(r.data, list):
                    ids += [x.get("dispute_id") or x.get("complaint_id") for x in r.data
                            if x.get("dispute_id") or x.get("complaint_id")]
            
            goal = {"kind": "answer", "offer_human": self._offer(state)}
            if note:
                goal["note"] = note
            
            return {
                "receipts": state["receipts"] + [r.receipt() for r in results],
                "allowed_ids": ids,
                "goal": goal,
                "route": {"next": "reply"}
            }
    
    def resolve_transaction(self, state: AgentState, config: RunnableConfig) -> dict:
        """Load transaction for dispute."""
        with tracer.start_as_current_span("resolve_transaction"):
            ctx = _ctx(config)
            try:
                r = self.d.read.get_transaction(ctx, state["run_id"], self._as_of(state), state["target_txn_id"])
            except (NotFound, ServingError):
                return {"goal": {"kind": "ask_clarification", "topic": "transaction", "options": []},
                        "route": {"next": "clarify"}}
            
            self._log(state, config, "resolve_transaction", "tool",
                     {"source": r.source, "transaction_id": r.data["transaction_id"]})
            
            ex = state.get("extraction") or {}
            statement = ex.get("customer_statement") or {"original": state["message"], "en": state["message"]}
            
            return {
                "txn": r.data,
                "statement": statement,
                "receipts": state["receipts"] + [r.receipt()],
                "route": {"next": "check_eligibility"}
            }
    
    def check_eligibility(self, state: AgentState, config: RunnableConfig) -> dict:
        """Evaluate dispute policy."""
        with tracer.start_as_current_span("check_eligibility"):
            txn, reason = state["txn"], state["dispute_reason"]
            existing = self.d.store.disputes.get(txn["transaction_id"])
            
            result = self.d.policy.evaluate(
                txn, reason, self._as_of(state),
                already_disputed=existing is not None,
                escalation=bool(state.get("escalated"))
            )
            
            checks = [asdict(r) for r in result.rules]
            self._log(state, config, "check_eligibility", "policy",
                     {"outcome": result.outcome, "rules": checks, "redirect": result.redirect},
                     {"policy": result.version})
            
            upd = {"policy_checks": checks}
            
            if result.outcome == "automated":
                return {
                    **upd,
                    "confirmation_summary": confirmation_summary(txn, reason, state["language"]),
                    "card_hash": _card_hash(txn, reason),
                    "route": {"next": "confirm"}
                }
            
            if result.outcome == "human_review":  # no customer confirmation on this path, so no card to check
                reasons = list(dict.fromkeys(state["reasons"] + result.triggers()))
                return {**upd, "reasons": reasons, "card_hash": "", "route": {"next": "file_dispute"}}
            
            if result.redirect == "explain_decline":
                return {**upd, "intent": "decline_explanation", "route": {"next": "answer_inquiry"}}
            
            if result.redirect == "already_disputed" and existing:
                return {**upd, **self._already_disputed(state, existing)}
            
            goal = {"kind": "answer", "note": result.redirect, "offer_human": self._offer(state)}
            if result.redirect == "out_of_window":  # the customer copy states the policy's window, not a constant
                goal["window_days"] = self.d.policy.cfg["window_days"]
            return {
                **upd,
                "goal": goal,
                "route": {"next": "reply"}
            }
    
    def confirm(self, state: AgentState, config: RunnableConfig) -> dict:
        """Set awaiting=confirmation."""
        goal = {"kind": "ask_confirmation", "fixed_block": state["confirmation_summary"]}
        if self._offer(state):
            goal["offer_human"] = True
        return {"goal": goal, "awaiting": "confirmation"}
    
    def file_dispute(self, state: AgentState, config: RunnableConfig) -> dict:
        """File the dispute."""
        with tracer.start_as_current_span("file_dispute"):
            ctx, as_of, lang = _ctx(config), self._as_of(state), state["language"]
            
            try:
                txn = self.d.read.get_transaction(ctx, state["run_id"], as_of, state["txn"]["transaction_id"]).data
                if state.get("card_hash") and _card_hash(txn, state["dispute_reason"]) != state["card_hash"]:
                    # "Sí" confirms exactly the card shown; the record behind it changed, so show the new card.
                    self._log(state, config, "file_dispute", "guard", {"error": "card changed since it was shown"})
                    return {"txn": txn, "card_hash": _card_hash(txn, state["dispute_reason"]),
                            "confirmation_summary": confirmation_summary(txn, state["dispute_reason"], lang),
                            "route": {"next": "confirm"}}
                res = self.d.write.create_dispute(
                    ctx, txn, state["dispute_reason"], state["statement"], as_of,
                    bool(state.get("escalated")), ctx.session_id, state["turn_id"], lang
                )
            except AlreadyDisputed as e:
                return self._already_disputed(state, e.existing)
            except PolicyRejected as e:
                return {"goal": {"kind": "answer", "note": e.result.redirect}, "route": {"next": "reply"}}
            except PermissionDenied:
                return {"goal": {"kind": "abstain", "offer_human": True}, "route": {"next": "reply"}}
            except (WriteFailed, NotFound, ServingError) as e:
                self._log(state, config, "file_dispute", "error", {"error": repr(e)})
                return {"reasons": state["reasons"] + ["dispute_write_failed"], "route": {"next": "handoff"}}
            
            rec, d = res.receipt(), res.data
            self._log(state, config, "file_dispute", "tool",
                     {"source": res.source, "dispute_id": d["dispute_id"], "route": d["route"]})
            
            action = {
                "action": "dispute_filed" if d["route"] == "automated" else "dispute_drafted",
                "result": d["status"],
                "receipt_id": rec["receipt_id"]
            }
            
            return {
                "filed": d,
                "receipts": state["receipts"] + [rec],
                "actions": state["actions"] + [action],
                "allowed_ids": state["allowed_ids"] + [d["dispute_id"]],
                "route": {"next": "verify"}
            }
    
    def verify(self, state: AgentState, config: RunnableConfig) -> dict:
        """Verify dispute was written correctly."""
        with tracer.start_as_current_span("verify"):
            res = self.d.write.verify_dispute(_ctx(config), state["filed"], self._as_of(state))
            
            self._log(state, config, "verify", "tool",
                     {"source": res.source, "verified": res.data["verified"],
                      "mismatches": res.data["mismatches"]})
            
            upd = {"receipts": state["receipts"] + [res.receipt()]}
            
            if not res.data["verified"]:
                return {**upd, "reasons": state["reasons"] + ["verification_failed"], "route": {"next": "handoff"}}
            
            if state["filed"]["route"] == "human_review":
                return {**upd, "route": {"next": "handoff"}}
            
            goal = {
                "kind": "answer",
                "note": "dispute_filed",
                "offer_human": self._offer(state),
                "fixed_block": dispute_filed(state["filed"]["dispute_id"], state["language"])
            }
            
            return {**upd, "goal": goal, "route": {"next": "reply"}}
    
    def clarify(self, state: AgentState, config: RunnableConfig) -> dict:
        """Set awaiting=clarification."""
        goal, lang = dict(state["goal"]), state["language"] if state["language"] in INTENT_LABELS else "es"
        topic, options = goal.get("topic"), goal.get("options") or []
        
        if topic == "transaction":
            by_id = {x["transaction_id"]: x for x in state.get("candidates") or []}
            display = [txn_option(by_id[o], lang) for o in options if o in by_id]
        elif topic == "intent":
            display = [INTENT_LABELS[lang][o] for o in options if o in INTENT_LABELS[lang]]
        elif topic == "dispute_reason":
            display = [REASON_LABELS[lang][o] for o in options if o in REASON_LABELS[lang]]
        else:
            display = []
        
        goal["display_options"] = display
        return {"goal": goal, "awaiting": "clarification", "clarification": {"topic": topic, "options": display}}
    
    def handoff(self, state: AgentState, config: RunnableConfig) -> dict:
        """Create handoff packet for human agent."""
        with tracer.start_as_current_span("handoff"):
            ctx, lang = _ctx(config), state["language"]
            codes = list(dict.fromkeys(state.get("reasons") or ["customer_request"]))
            request_en = (state.get("extraction") or {}).get("english_gloss") or state["message"]
            
            questions = []
            try:
                questions, call = open_questions(self.d.llm_client, self.d.models["compose"],
                                                request_en, codes, state["receipts"])
                self._log(state, config, "handoff", "llm",
                         {"role": "open_questions", "output": questions, "usage": call.usage},
                         {"model": call.model, "prompt": call.prompt_version}, call.latency_ms)
            except LLMError as e:
                self._log(state, config, "handoff", "error", {"role": "open_questions", "error": str(e)})
            
            packet = build_packet(
                session_id=ctx.session_id,
                customer_id=ctx.customer_id,
                language=lang if lang in ("es", "pt") else "es",
                data_as_of=state.get("as_of") or "",
                reason_codes=codes,
                customer_request={"original": state["message"], "en": request_en},
                receipts=state["receipts"],
                actions=state["actions"],
                decisions=state.get("decisions") or [],
                policy_checks=state.get("policy_checks") or [],
                open_questions=questions,
                now=datetime.now(timezone.utc)
            )
            
            try:
                res = self.d.write.create_handoff(ctx, packet.model_dump(), state.get("as_of") or "")
            except HandoffFailed as e:
                self._log(state, config, "handoff", "error", {"role": "handoff", "error": str(e)})
                return {
                    "goal": {"kind": "handoff_failed", "fixed_block": handoff_failed(lang)},
                    "awaiting": "none",
                    "route": {"next": "reply"}
                }
            
            rec = res.receipt()
            self._log(state, config, "handoff", "tool",
                     {"source": "handoffs", "handoff_id": packet.handoff_id,
                      "priority": packet.priority, "reason_codes": codes})
            
            action = {"action": "handoff_created", "result": "open", "receipt_id": rec["receipt_id"]}
            
            return {
                "receipts": state["receipts"] + [rec],
                "actions": state["actions"] + [action],
                "allowed_ids": state["allowed_ids"] + [packet.handoff_id],
                "awaiting": "none",
                "goal": {"kind": "handoff_notice", "fixed_block": handoff_notice(packet.handoff_id, lang)},
                "route": {"next": "reply"}
            }
    
    def reply(self, state: AgentState, config: RunnableConfig) -> dict:
        """Compose and verify reply."""
        with tracer.start_as_current_span("reply"):
            lang, receipts = state["language"], state.get("receipts") or []
            goal = dict(state.get("goal") or {"kind": "error"})
            
            queue, offered = list(state.get("queue") or []), None
            if queue and state.get("awaiting", "none") == "none" and goal.get("kind") in (
                "answer", "greeting", "dispute_cancelled"
            ):
                offered = queue.pop(0)
                goal["queued_offer"] = offered
            
            text = None
            if self._over_budget(config):
                self._log(state, config, "reply", "error", {"error": "turn budget exceeded"})
            else:
                text = self._compose_verified(state, config, goal, receipts, lang)
            
            if text is None:
                text = fallback_reply(goal, receipts, lang)
                self._log(state, config, "reply", "template", {"goal": goal.get("kind")})
                logger.warning("reply fell back to template", extra={"goal": goal.get("kind")})  # CloudWatch alarm
            
            if goal.get("fixed_block"):
                text = f"{text}\n\n{goal['fixed_block']}"
            
            reply = {
                "reply_text": text,
                "language": lang,
                "awaiting": state.get("awaiting", "none"),
                "options": goal.get("display_options", []),
                "refs": _refs(receipts),
                "data_as_of": state.get("as_of")
            }
            if reply["awaiting"] == "confirmation" and state.get("txn"):
                reply["summary"] = {**confirmation_payload(state["txn"], state.get("dispute_reason")),
                                    "card_hash": state.get("card_hash")}  # the button sends confirm:<card_hash>
            
            recent = ((state.get("recent") or []) + [{"customer": state["message"], "assistant": text}])[-2:]
            
            return {"reply": reply, "recent": recent, "queue": queue, "queued_offer": offered, "goal": goal}
    
    def _compose_verified(self, state, config, goal, receipts, lang) -> str | None:
        """Compose reply and verify claims. Returns None if verification fails."""
        allowed, feedback = set(state.get("allowed_ids") or []), None
        
        for draft in range(2):  # First draft + one regeneration
            if draft and self._over_budget(config):  # no time left for a regeneration: the template answers
                self._log(state, config, "reply", "error", {"error": "turn budget exceeded before regeneration"})
                return None
            # The BFF stops waiting at 25 s: a compose that starts late only gets what is left of the turn budget.
            left = config["configurable"].get("deadline", float("inf")) - self.d.clock()
            cfg = self.d.models["compose"]
            cfg = replace(cfg, timeout_s=max(1.0, min(cfg.timeout_s, left)))
            try:
                composed, call = compose(self.d.llm_client, cfg, goal, receipts, lang, feedback,
                                         (state.get("extraction") or {}).get("english_gloss"))
            except LLMError as e:
                self._log(state, config, "reply", "error", {"role": "compose", "error": str(e)})
                return None
            
            self._log(state, config, "reply", "llm",
                     {"role": "compose", "claims": composed.claims, "usage": call.usage},
                     {"model": call.model, "prompt": call.prompt_version}, call.latency_ms)
            
            leaked = unknown_ids(composed.reply_text, allowed)
            if leaked:
                self._log(state, config, "reply", "guard", {"unknown_ids": sorted(leaked)})
                # Say where: "not in the receipts" made the model also blank its claims' receipt_ids (Jev then fails all)
                feedback = [f"reply_text must not contain these identifiers: {sorted(leaked)}. Remove them from "
                            "reply_text only; keep citing receipt_ids in claims."]
                continue
            
            try:
                vstate, vqs = build_verify_request(self.d.verify_qs, receipts, composed.claims, composed.reply_text)
                res = self.d.jev.decide(vstate, vqs)
                outcome = parse_verify(res, self.d.thresholds)
            except JevError as e:
                self._log(state, config, "reply", "error", {"role": "verify_reply", "error": str(e)})
                return None
            
            self._log(state, config, "reply", "jev",
                     {"verify": asdict(outcome), "usage": res.usage},
                     {"question_set": self.d.verify_qs["version"],
                      "thresholds": self.d.thresholds.version, "model": res.model},
                     res.latency_ms)
            
            if outcome.ok:
                return composed.reply_text
            
            feedback = [f"Unsupported claim: {composed.claims[i]['claim_en']}" for i in outcome.failed_claims
                       if i < len(composed.claims)]
            if outcome.promises_unverified:
                feedback.append("Do not promise refunds, deadlines or outcomes that no receipt shows.")
        
        return None
    
    def await_customer(self, state: AgentState, config: RunnableConfig) -> dict:
        """Pause graph and wait for customer input (LangGraph interrupt)."""
        resumed = interrupt(state["reply"])
        return {"message": resumed["message"], "turn_id": resumed["turn_id"]}
