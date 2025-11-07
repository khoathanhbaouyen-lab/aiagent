import chainlit as cl

@cl.on_chat_start
async def start():
    try:
        print("Attempting to run_js...")
        res = await cl.run_js(
            "console.log('Test from run_js'); localStorage.setItem('TEST_TOKEN', '12345'); return 'Success';"
        )
        print(f"run_js result: {res}")
        await cl.Message(content=f"JS Result: {res}").send()
    except Exception as e:
        print(f"run_js FAILED: {e}")
        await cl.Message(content=f"run_js FAILED: {e}").send()