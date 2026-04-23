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

Note:

- this smoke test intentionally disables the live Gemini client
- it uses the local fallback model so the test can run without network access
- use a separate integration test if you want to verify the real Gemini endpoint

```powershell
@'
from japan_rental_agent.agent import AgentDependencies, RentalAgentService
from japan_rental_agent.agent.llm import FallbackAgentModel
from japan_rental_agent.config import AppConfig
from japan_rental_agent.contracts import AgentRequest

config = AppConfig(llm_api_key=None)
default_dependencies = AgentDependencies.from_config(config)
service = RentalAgentService(
    config=config,
    dependencies=AgentDependencies(
        config=config,
        agent_model=FallbackAgentModel(),
        parser_tool=None,
        search_tool=default_dependencies.search_tool,
        enrichment_tool=default_dependencies.enrichment_tool,
        ranking_tool=default_dependencies.ranking_tool,
    ),
)
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
reply=I found 0 rental candidates that match the current request.
tools=search,llm.ranking_plan,enrichment,ranking,llm.response
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
