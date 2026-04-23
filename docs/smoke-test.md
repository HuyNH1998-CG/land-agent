# Smoke Test Guide

This project has a minimal smoke test flow to confirm that:

- dependencies are installed
- the package can be imported
- the LangGraph workflow boots
- the agent service returns a valid response

## 1. Install dependencies

Run this once after creating a new environment:

```powershell
python -m pip install -e .[dev]
```

## 2. Run the pytest smoke test

This checks that the service boots and returns a valid response shape.

```powershell
python -m pytest tests/test_smoke_imports.py -q
```

Expected result:

```text
1 passed
```

## 3. Run a direct agent smoke test

This calls the service directly and prints a short result summary.

```powershell
@'
from japan_rental_agent.agent import RentalAgentService
from japan_rental_agent.contracts import AgentRequest

service = RentalAgentService()
response = service.handle_request(
    AgentRequest(
        session_id="smoke",
        message="Find me a rental in Tokyo under 80000 yen near station",
    )
)

print("status=" + response.status)
print("reply=" + response.reply)
print("tools=" + ",".join(response.meta.tool_used))
'@ | python -
```

Expected result right now:

```text
status=success
reply=Project skeleton is ready. Search logic has not been implemented yet.
tools=parser,search,enrichment,ranking
```

## 4. Optional UI smoke test

If you want to confirm the Streamlit entrypoint boots:

```powershell
streamlit run ui/app.py
```

Then open the local URL shown in the terminal.

## 5. One-command rerun

You can also use the helper script:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\smoke_test.ps1
```

