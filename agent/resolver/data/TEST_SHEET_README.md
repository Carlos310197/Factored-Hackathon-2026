# Writing the resolver test set (for Andrés)

Spec: the resolver design spec §5.4 (`docs/design/`). You write these messages **blind**:
please do not look at the resolver code, `simulate.yaml`, the dev set or any model output before you finish.

Open `test_sheet_v1.csv` (150 rows) in Google Sheets or Excel. For each row, write the `message` column: one message
a customer would send to the bank's chat about the transaction in `describe_this`.

- Write in the row's `lang` (`es` = Latin American Spanish, `pt` = Brazilian Portuguese), 1–3 sentences, informally,
  the way real customers write (typos and abbreviations are fine).
- Follow `style_hint` (for example "don't say the amount; say when loosely ('last week')"). It decides which details
  you give. Do not add details the hint says to leave out.
- `candidates` lists everything the customer has in the window. On some rows the `instruction` asks you to describe
  a transaction that is **not** in the list: write as if you believe it is yours.
- Vary the goal: sometimes you want to dispute the charge, sometimes you only ask what happened.
- Do not copy the `describe_this` text; say it as a customer would ("el retiro del cajero del martes", "uns 340 reais").

Save as CSV (any delimiter is fine) and send it back as `test_sheet_v1_completed.csv`. Carlos will record its SHA-256
in `context/progress-tracker.md` before anything is evaluated on it.
