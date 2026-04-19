from langchain_ollama.llms import OllamaLLM
from langchain_core.prompts import ChatPromptTemplate

model = OllamaLLM(model="gemma:7b")

template = """
You are a chatbot and your goal is to reduce the volume of routine queries reaching
human support staff by allowing users to query you. You use documentation we give you.

Here is the relevant documentation: {doc}

Here is the question to answer: {question}
"""


prompt = ChatPromptTemplate.from_template(template)
chain = prompt | model


def get_response(question):

    llm_result = chain.invoke({
        "doc": [],
        "question": question
    })

    return llm_result