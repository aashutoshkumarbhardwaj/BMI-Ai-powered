import streamlit as st
import os
from langchain_openai import ChatOpenAI # This is unused, but kept for potential future use
from dotenv import load_dotenv
from langgraph.graph import StateGraph, START, END
from typing import TypedDict
from llama_index.core import Document, VectorStoreIndex, Settings
from llama_index.llms.openai import OpenAI as LlamaOpenAI
from llama_index.embeddings.openai import OpenAIEmbedding


# --- BMI Calculation Graph ---
class BMIState(TypedDict):
    weight_kg: float
    height_m: float
    bmi: float
    category: str


def calculate_bmi(state: BMIState) -> BMIState:
    """Calculates BMI from weight and height."""
    weight = state["weight_kg"]
    height = state["height_m"]
    if height > 0:
        bmi = weight / (height**2)
        state["bmi"] = round(bmi, 2)
    else:
        state["bmi"] = 0
    return state


def label_bmi(state: BMIState) -> BMIState:
    """Assigns a BMI category based on the BMI value."""
    bmi = state["bmi"]
    if bmi < 18.5:
        state["category"] = "Underweight"
    elif bmi < 25:
        state["category"] = "Normal"
    elif bmi < 30:
        state["category"] = "Overweight"
    else:
        state["category"] = "Obese"
    return state


def get_bmi_workflow():
    """Builds and compiles the BMI calculation LangGraph workflow."""
    graph = StateGraph(BMIState)
    graph.add_node("calculate_bmi", calculate_bmi)
    graph.add_node("label_bmi", label_bmi)
    graph.add_edge(START, "calculate_bmi")
    graph.add_edge("calculate_bmi", "label_bmi")
    graph.add_edge("label_bmi", END)
    return graph.compile()


# --- LLM Q&A Graph ---
class LLMState(TypedDict):
    question: str
    answer: str


def get_llm_workflow():
    """Builds and compiles the LLM Q&A LangGraph workflow."""
    load_dotenv() # Loads variables from .env file

    # 1. Create sample documents about health and BMI
    documents = [
        Document(
            text="A BMI under 18.5 is considered underweight. It may indicate malnutrition or other health issues. It's advisable to consult a doctor to understand the underlying causes and get a personalized nutrition plan."
        ),
        Document(
            text="A BMI between 18.5 and 24.9 is considered normal and healthy. Maintaining a balanced diet and regular physical activity is key to staying in this range."
        ),
        Document(
            text="A BMI between 25.0 and 29.9 is considered overweight. This increases the risk of developing chronic diseases like heart disease and diabetes. A combination of a healthier diet and increased exercise is recommended."
        ),
        Document(
            text="A BMI of 30.0 or higher is considered obese. Obesity is a serious health condition that significantly increases the risk of many chronic diseases. It is highly recommended to consult a healthcare professional for a comprehensive weight management plan."
        ),
    ]

    # 2. Configure LlamaIndex components to use OpenRouter
    api_key = os.getenv("OPENAI_API_KEY")
    api_base = "https://openrouter.ai/api/v1"

    # Configure the LLM for chat/query
    llm = LlamaOpenAI(
        model="openai/gpt-3.5-turbo", # Use the OpenRouter model string
        api_key=api_key,
        api_base=api_base,
        temperature=0,
    )

    # Configure the embedding model for indexing
    embed_model = OpenAIEmbedding(
        model="text-embedding-ada-002", api_key=api_key, api_base=api_base
    )
    index = VectorStoreIndex.from_documents(documents, embed_model=embed_model)

    # 3. Create a query engine
    query_engine = index.as_query_engine(llm=llm)

    def llm_qa(state: LLMState) -> LLMState:
        """Uses an LLM to answer a question."""
        question = state["question"]
        # Use the LlamaIndex query engine to get the answer
        response = query_engine.query(question)
        answer = str(response)
        state["answer"] = answer
        return state

    graph = StateGraph(LLMState)
    graph.add_node("llm_qa", llm_qa)
    graph.add_edge(START, "llm_qa")
    graph.add_edge("llm_qa", END)
    return graph.compile()


# --- Streamlit Application ---
def main():
    st.set_page_config(page_title="BMI and Health Assistant", layout="wide")
    st.title("BMI and Health Assistant")

    # --- Workflows ---
    bmi_workflow = get_bmi_workflow()
    llm_workflow = get_llm_workflow()

    # --- UI Layout ---
    col1, col2 = st.columns(2)

    with col1:
        st.header("BMI Calculator")
        st.write("Enter your weight and height to calculate your BMI.")

        weight = st.number_input("Weight (kg)", min_value=0.0, value=70.0, step=0.5)
        height = st.number_input("Height (m)", min_value=0.0, value=1.75, step=0.01)

        if st.button("Calculate BMI"):
            if height > 0:
                initial_state = {"weight_kg": weight, "height_m": height}
                final_state = bmi_workflow.invoke(initial_state)
                st.metric(label="Your BMI", value=final_state["bmi"])
                st.info(f"Category: **{final_state['category']}**")

                st.subheader("Calculation Flow")
                st.write(
                    "This diagram shows the steps taken to calculate and categorize your BMI."
                )
                # Generate and display the graph
                graph_image = bmi_workflow.get_graph().draw_mermaid_png()
                st.image(graph_image, caption="BMI Calculation Graph")
            else:
                st.error("Height must be greater than zero.")

    with col2:
        st.header("Health Q&A")
        st.write("Ask a question about BMI, health, or nutrition.")
        question = st.text_input("Your Question:", "What are some hints for an overweight person?")

        if st.button("Get Answer"):
            with st.spinner("Thinking..."):
                initial_state = {"question": question}
                final_state = llm_workflow.invoke(initial_state)
                st.markdown(final_state["answer"])


if __name__ == "__main__":
    main()
