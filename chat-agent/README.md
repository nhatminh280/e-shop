# E-Shop LangGraph Chat Agent

Small standalone LangGraph workflow for trying an e-shop chatbot flow before wiring it into the Java backend.

## Workflow

```text
START
  -> classify_intent
  -> collect_slots
  -> product_search | order_status | cart_action | handoff | general
  -> answer
END
```

The demo uses mock catalog and order data so it can run without database access or an LLM API key.

## Run

```powershell
cd chat-agent
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m uvicorn app:app --reload --port 8010
```

Try it:

```powershell
Invoke-RestMethod -Method Post `
  -Uri http://127.0.0.1:8010/chat `
  -ContentType application/json `
  -Body '{"session_id":"demo","message":"ao size M mau den con hang khong?"}'
```

More examples:

```json
{"session_id":"demo","message":"check order ES123"}
{"session_id":"demo","message":"add jacket to cart"}
{"session_id":"demo","message":"toi muon gap nhan vien support"}
```

## Next integration step

Replace `mock_catalog.py` with API calls to the Spring Boot endpoints:

- `GET /api/catalog/products/search?q=...`
- `GET /api/catalog/products/filter?...`
- authenticated cart endpoint `POST /api/cart/items`
- support conversation endpoints under `/api/support`
