"""Fixed ES/PT texts inserted verbatim (confirmation summary, handoff notice, auth messages) and the deterministic
fallback reply used when Claude or the reply verification fails. No model writes these."""

INTENT_LABELS = {
    "es": {"account_info": "información de tus cuentas", "transaction_status": "el estado de una transacción",
           "decline_explanation": "por qué rechazaron un pago", "dispute_charge": "disputar un cargo",
           "dispute_status": "el estado de una disputa o reclamo", "unsupported": "otra solicitud"},
    "pt": {"account_info": "informações das suas contas", "transaction_status": "o status de uma transação",
           "decline_explanation": "por que um pagamento foi recusado", "dispute_charge": "contestar uma cobrança",
           "dispute_status": "o status de uma contestação ou reclamação", "unsupported": "outra solicitação"},
}
REASON_LABELS = {
    "es": {"duplicate_charge": "cobro duplicado", "wrong_amount": "monto incorrecto",
           "not_received": "producto o servicio no recibido", "cancelled_but_charged": "cancelado pero cobrado",
           "unauthorized": "cargo no reconocido"},
    "pt": {"duplicate_charge": "cobrança duplicada", "wrong_amount": "valor incorreto",
           "not_received": "produto ou serviço não recebido", "cancelled_but_charged": "cancelado mas cobrado",
           "unauthorized": "cobrança não reconhecida"},
}
# Dataset enums are English (typed_products / typed_transactions); unknown values pass through unchanged.
STATUS_LABELS = {
    "es": {"Active": "Activa", "Blocked": "Bloqueada", "Closed": "Cerrada", "Suspended": "Suspendida",
           "Approved": "Aprobada", "Declined": "Rechazada", "Pending": "Pendiente", "Reversed": "Revertida"},
    "pt": {"Active": "Ativa", "Blocked": "Bloqueada", "Closed": "Encerrada", "Suspended": "Suspensa",
           "Approved": "Aprovada", "Declined": "Recusada", "Pending": "Pendente", "Reversed": "Estornada"},
}
FALLBACK = {
    "es": {"answer": "Esto es lo que encontré:", "ask_clarification": "¿Me ayudas a precisar tu solicitud?",
           "ask_confirmation": "¿Confirmas que registre esta disputa?",
           "handoff_notice": "Voy a transferir tu caso a un especialista.", "handoff_failed": "",
           "abstain": "No puedo ayudarte con eso por este canal. Puedo ayudarte con tus cuentas, transacciones, "
                      "pagos rechazados y disputas.",
           "refuse_injection": "Solo puedo ayudarte con tus propias cuentas y con las solicitudes que atiendo aquí.",
           "greeting": "¡Hola! ¿En qué puedo ayudarte con tus cuentas o pagos?",
           "dispute_cancelled": "Entendido, no registré la disputa.",
           "data_unavailable": "No puedo acceder a tu información en este momento.",
           "error": "Tuve un problema procesando tu mensaje."},
    "pt": {"answer": "Isto é o que encontrei:", "ask_clarification": "Pode me ajudar a detalhar sua solicitação?",
           "ask_confirmation": "Você confirma que devo registrar esta contestação?",
           "handoff_notice": "Vou transferir seu caso para um especialista.", "handoff_failed": "",
           "abstain": "Não posso ajudar com isso por este canal. Posso ajudar com suas contas, transações, "
                      "pagamentos recusados e contestações.",
           "refuse_injection": "Só posso ajudar com suas próprias contas e com as solicitações que atendo aqui.",
           "greeting": "Olá! Como posso ajudar com suas contas ou pagamentos?",
           "dispute_cancelled": "Entendido, não registrei a contestação.",
           "data_unavailable": "Não consigo acessar suas informações neste momento.",
           "error": "Tive um problema ao processar sua mensagem."},
}
NOTES = {
    "es": {"not_declined": "Esa transacción no fue rechazada.",
           "wait_pending": "La transacción sigue pendiente; podrás disputarla cuando se registre.",
           "already_reversed": "Esa transacción ya fue reversada.",
           "not_disputable_type": "Ese tipo de movimiento no se puede disputar por este canal.",
           "out_of_window": "La transacción supera el plazo de 60 días para disputas.",
           "already_disputed": "Ya existe una disputa para esa transacción.",
           "dispute_filed": "Registré tu disputa.", "not_disputable": "Esa transacción no se puede disputar."},
    "pt": {"not_declined": "Essa transação não fue recusada.",
           "wait_pending": "A transação ainda está pendente; você poderá contestá-la quando for registrada.",
           "already_reversed": "Essa transação já foi estornada.",
           "not_disputable_type": "Esse tipo de movimentação não pode ser contestado por este canal.",
           "out_of_window": "A transação ultrapassa o prazo de 60 dias para contestações.",
           "already_disputed": "Já existe uma contestação para essa transação.",
           "dispute_filed": "Registrei sua contestação.", "not_disputable": "Essa transação não pode ser contestada."},
}
OFFER_HUMAN = {"es": "¿Quieres que te comunique con un especialista?", "pt": "Quer que eu te conecte com um especialista?"}
QUEUED = {"es": "¿Quieres que también te ayude con tu otra solicitud?", "pt": "Quer ajuda também com sua outra solicitação?"}
AUTH = {
    "es": {"auth_required": "Para ayudarte necesito que inicies sesión.",
           "session_expired": "Tu sesión expiró. Inicia sesión de nuevo para continuar.",
           "invalid_message": "No pude leer tu mensaje. Escríbelo de nuevo, por favor (máximo 2000 caracteres)."},
    "pt": {"auth_required": "Para ajudar, preciso que você faça login.",
           "session_expired": "Sua sessão expirou. Faça login novamente para continuar.",
           "invalid_message": "Não consegui ler sua mensagem. Escreva novamente, por favor (máximo 2000 caracteres)."},
}
NO_DECIMALS = {"COP"}


def _lang(lang: str) -> str:
    return lang if lang in FALLBACK else "es"


def fmt_money(amount, currency: str) -> str:
    a = float(amount)
    return f"{a:,.0f} {currency}" if currency in NO_DECIMALS else f"{a:,.2f} {currency}"


def confirmation_summary(txn: dict, reason: str, lang: str) -> str:
    lang = _lang(lang)
    merchant = txn.get("merchant_name") or txn.get("transaction_type")
    day, money, label = str(txn["process_date"])[:10], fmt_money(txn["amount"], txn["currency"]), REASON_LABELS[lang][reason]
    if lang == "pt":
        return (f"Resumo da contestação:\n• Transação: {merchant} em {day}\n• Valor: {money}\n• Motivo: {label}\n"
                "Responda «sim, confirmo» para registrá-la ou diga o que deseja mudar.")
    return (f"Resumen de la disputa:\n• Transacción: {merchant} del {day}\n• Monto: {money}\n• Motivo: {label}\n"
            "Responde «sí, confirmo» para registrarla o dime qué quieres cambiar.")


def handoff_notice(ref: str, lang: str) -> str:
    if _lang(lang) == "pt":
        return f"Referência do seu caso: {ref}. Um especialista vai analisar sua solicitação."
    return f"Referencia de tu caso: {ref}. Un especialista revisará tu solicitud."


def dispute_filed(dispute_id: str, lang: str) -> str:
    if _lang(lang) == "pt":
        return f"Número da contestação: {dispute_id} (status: registrada)."
    return f"Número de disputa: {dispute_id} (estado: registrada)."


def handoff_failed(lang: str) -> str:
    if _lang(lang) == "pt":
        return "Não consegui transferir seu caso agora. Por favor, entre em contato com nossa central por telefone."
    return "No pude transferir tu caso en este momento. Por favor comunícate con nuestra línea de atención telefónica."


def auth_message(kind: str, lang: str) -> str:
    return AUTH[_lang(lang)][kind]


def _status(value, lang: str):
    return STATUS_LABELS[_lang(lang)].get(value, value)


def _facts(receipt: dict, lang: str) -> list[str]:
    src, data = receipt["source"], receipt["data"]
    if src == "dim_product":
        return [f"{d['product_type']} ****{d['product_last4']}: {fmt_money(d['current_balance'], d['currency'])} "
                f"({_status(d['product_status'], lang)})" for d in data]
    if src == "fct_transaction" and isinstance(data, dict):
        merchant = data.get("merchant_name") or data.get("transaction_type")
        return [f"{merchant} {str(data['process_date'])[:10]}: {_status(data['transaction_status'], lang)}, "
                f"{fmt_money(data['amount'], data['currency'])}"]
    if src == "seed_decline_reason":
        text = data.get(f"customer_text_{lang}")
        return [text] if text else []
    if src == "disputes" and isinstance(data, list):
        return [f"{d['dispute_id']}: {d['status']}" for d in data]
    if src == "fct_complaint":
        return [f"{c['complaint_id']}: {c['status']}" for c in data]
    return []


def fallback_reply(goal: dict, receipts: list[dict], lang: str) -> str:
    lang = _lang(lang)
    kind = goal.get("kind", "error")
    parts = [FALLBACK[lang].get(kind, FALLBACK[lang]["error"])]
    if goal.get("note"):
        parts.append(NOTES[lang].get(goal["note"], ""))
    if kind == "answer":
        parts += [f"• {line}" for r in receipts for line in _facts(r, lang)]
    if kind == "ask_clarification":
        parts += [f"• {o}" for o in goal.get("display_options", [])]
    if goal.get("offer_human") or kind in ("data_unavailable", "error", "abstain"):
        parts.append(OFFER_HUMAN[lang])
    if goal.get("queued_offer"):
        parts.append(QUEUED[lang])
    return "\n".join(p for p in parts if p)
