from langchain_community.chat_models import ChatPerplexity
from langchain.chains import LLMChain
from langchain.memory import ConversationBufferWindowMemory
from langchain.prompts.chat import (
    ChatPromptTemplate,
    SystemMessagePromptTemplate,
    HumanMessagePromptTemplate,
)
import os
from dotenv import find_dotenv, load_dotenv

load_dotenv(find_dotenv())

PPLX_API_KEY = os.getenv("PPLX_API_KEY")


def draft_email(user_input, team_id, name="User"):
    """
    Generates an email draft using a language model, maintaining a conversation history
    specific to each Slack team and including the last 5 exchanges in the prompt.

    Args:
        user_input (str): The user's input for generating the email draft.
        team_id (str): The Slack team ID, used to maintain separate conversation histories
                         for each team.
        name (str): The user's name (optional).

    Returns:
        str: The generated email draft.
    """

    # Use team_id as a key for separate memory for each team
    if not hasattr(draft_email, "memories"):
        draft_email.memories = {}

    if team_id not in draft_email.memories:
        draft_email.memories[team_id] = ConversationBufferWindowMemory(k=5, memory_key="conversation_history")

    memory = draft_email.memories[team_id]

    # Get the conversation history from the memory
    conversation_history = memory.load_memory_variables({})['conversation_history']

    chat = ChatPerplexity(
        model="llama-3.1-sonar-small-128k-online",
        temperature=1,
        pplx_api_key=PPLX_API_KEY,
    )

    template = """
    You are a helpful assistant, named Vishoo's Droid that engages in conversation and answers the user's queries based on their queries.
    Here's the conversation history:
    {conversation_history}
    Based on the above conversation history, respond to the following user input:
    {user_input}
    Provide clear and concise responses.
    Think twice before you answer and make sure youre being a good and polite helpful assistant, dont mention the citation numbers, and take care of the conversation history as well.
    """
    system_message_prompt = SystemMessagePromptTemplate.from_template(template)
    human_template = "{user_input}"
    human_message_prompt = HumanMessagePromptTemplate.from_template(human_template)

    chat_prompt = ChatPromptTemplate.from_messages(
        [system_message_prompt, human_message_prompt]
    )

    chain = LLMChain(llm=chat, prompt=chat_prompt, memory=memory)
    response = chain.run(user_input=user_input, conversation_history=conversation_history)

    return response
