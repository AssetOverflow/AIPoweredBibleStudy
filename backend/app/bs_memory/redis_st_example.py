from redis_short_term import *


async def main():
    memory = ChatMemory(redis_url="redis://localhost")
    await memory.connect()

    # Start a session
    session_id = "session_12345"
    await memory.start_session(session_id, topic="Bible Study")

    # Log messages
    await memory.log_message(session_id, "User", "Can you explain the concept of grace?")
    await memory.log_message(session_id, "Agent", "Grace is God's unmerited favor...")

    # Retrieve recent messages
    messages = await memory.get_recent_messages(session_id, count=2)
    print("Recent Messages:", messages)

    # Retrieve metadata
    metadata = await memory.get_metadata(session_id)
    print("Session Metadata:", metadata)

    # End session
    await memory.end_session(session_id)

    await memory.close()


# Run the example
asyncio.run(main())