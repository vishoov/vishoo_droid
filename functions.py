import os
from langchain_community.chat_models import ChatPerplexity
from langchain.chains import LLMChain
from langchain.memory import ConversationBufferWindowMemory
from langchain.prompts.chat import (
    ChatPromptTemplate,
    SystemMessagePromptTemplate,
    HumanMessagePromptTemplate,
)
from dotenv import find_dotenv, load_dotenv

load_dotenv(find_dotenv())

def draft_email(user_input, name="User"):
    # Create a persistent conversation memory attribute on the function if it doesn't exist.
    if not hasattr(draft_email, "memory"):
        draft_email.memory = ConversationBufferWindowMemory(k=5, memory_key="conversation_history")

    # Instantiate ChatPerplexity with the required model, temperature, and API key.
    chat = ChatPerplexity(
        model="llama-3.1-sonar-small-128k-online",
        temperature=1,
        pplx_api_key=os.getenv("PPLX_API_KEY"),
    )

    # Define a system prompt that instructs the assistant to behave as a helpful conversational assistant.
    template = """
    You are a helpful assistant that engages in conversation and answers the user's queries based on the context provided.
    Refer to the conversation history below:
    {conversation_history}
    Provide clear and concise responses.
    """
    system_message_prompt = SystemMessagePromptTemplate.from_template(template)
    human_template = "{user_input}"
    human_message_prompt = HumanMessagePromptTemplate.from_template(human_template)
    
    chat_prompt = ChatPromptTemplate.from_messages(
        [system_message_prompt, human_message_prompt]
    )
    
    # Create an LLMChain with the conversation memory to keep last 5 exchanges.
    chain = LLMChain(llm=chat, prompt=chat_prompt, memory=draft_email.memory)
    response = chain.run(user_input=user_input)
    
    return response
