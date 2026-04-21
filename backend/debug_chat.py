import asyncio, traceback
from backend.services.data_service import data_service
from backend.agents.gdelt_agent import GDELTAgent

async def test():
    await data_service.initialize()
    agent = GDELTAgent(data_service)
    try:
        result = await agent.chat('Give me a daily brief for January 15 2024')
        print('SUCCESS:', result['reply'][:200])
    except Exception as e:
        print(f"ERROR: {type(e).__name__}: {repr(e)}")
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test())
