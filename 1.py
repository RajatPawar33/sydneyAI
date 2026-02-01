from langchain_community.chat_models import ChatOllama

llm = ChatOllama(model="llama3:8b")
print(llm.invoke("Say hello in one line").content)
