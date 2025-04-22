import os
import json
from langchain_google_vertexai import ChatVertexAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
from langchain_community.chat_message_histories import MongoDBChatMessageHistory
from langchain.memory import ConversationBufferMemory
from langchain.chains import ConversationChain
from dotenv import load_dotenv

load_dotenv()

llm = ChatVertexAI(model="gemini-2.0-flash-001", temperature=0.7)

def build_react_chat_agent(idea_id: str, idea_description: str, roi: float, effort: float, user_id: str, mongo_uri: str = "mongodb://localhost:27017"):
    """Creates a ReAct-style agent that remembers conversation per idea/user."""
    
    # MongoDB-backed message history (chat memory)
    session_id = f"{user_id}_{idea_id}"
    history = MongoDBChatMessageHistory(
        connection_string=mongo_uri,
        session_id=session_id,
        database_name="thinkwise_chat",
        collection_name="memory"
    )

    memory = ConversationBufferMemory(
        memory_key="chat_history",
        return_messages=True,
        chat_memory=history
    )

    prompt = ChatPromptTemplate.from_messages([
        ("system", f"""
You are an assistant helping users evaluate their business idea. The idea is:

Description: {idea_description}
ROI Score: {roi}
Effort Score: {effort}

Start the conversation by answering the user's question or collecting feedback on this idea.
"""),
        MessagesPlaceholder(variable_name="chat_history"),
        ("human", "{input}")
    ])

    chain = ConversationChain(
        llm=llm,
        prompt=prompt,
        memory=memory,
        output_parser=StrOutputParser(),
        verbose=True
    )

    return chain
