import streamlit as st
import os
import pandas as pd
import plotly.graph_objects as go
from langchain_openai import ChatOpenAI # This is unused, but kept for potential future use
from dotenv import load_dotenv
from langgraph.graph import StateGraph, START, END
from typing import TypedDict, Any
from llama_index.core import Document, VectorStoreIndex, Settings
from llama_index.llms.openai import OpenAI as LlamaOpenAI
from llama_index.embeddings.openai import OpenAIEmbedding


# --- BMI Calculation Graph ---
class BMIState(TypedDict):
    weight_kg: float
    height_cm: float
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
    api_key = os.getenv("OPENAI_API_KEY")   # Your OpenRouter API key
    api_base = "https://openrouter.ai/api/v1"

    llm = LlamaOpenAI(
    model="gpt-4o-mini",
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


def get_insights_workflow():
    """Builds and compiles the LLM insights LangGraph workflow."""
    load_dotenv()

    api_key = os.getenv("OPENAI_API_KEY")
    api_base = "https://openrouter.ai/api/v1"

    llm: Any = LlamaOpenAI(
    model="gpt-3.5-turbo",
    api_key=api_key,
    api_base=api_base,
    temperature=0.7,
)

    class InsightState(TypedDict):
        user_data: str
        insight: str

    def generate_insight(state: InsightState) -> InsightState:
        """Generates health insights based on user data."""
        user_data = state["user_data"]
        prompt = f"""
        As a friendly and encouraging AI health assistant, analyze the following user data and provide 2-3 concise, actionable, and positive insights.
        Focus on encouragement and practical tips. Do not give strict medical advice.
        Keep the tone light and supportive. Use emojis.

        User Data:
        {user_data}

        Example Insight Format:
        - 💡 **Insight 1:** Your brief, encouraging insight.
        - 🌱 **Insight 2:** Another brief, encouraging insight.

        Generate the insights now.
        """
        response = llm.complete(prompt)
        state["insight"] = str(response)
        return state

    graph = StateGraph(InsightState)
    graph.add_node("generate_insight", generate_insight)
    graph.add_edge(START, "generate_insight")
    graph.add_edge("generate_insight", END)
    return graph.compile()


def get_journey_insight_workflow():
    """Builds a workflow to generate a narrative for a specific health journey stage."""
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY")
    api_base = "https://openrouter.ai/api/v1"

    llm: Any = LlamaOpenAI(
    model="gpt-3.5-turbo",
    api_key=api_key,
    api_base=api_base,
    temperature=0.7,
)

    class JourneyState(TypedDict):
        journey_data: str
        narrative: str

    def generate_narrative(state: JourneyState) -> JourneyState:
        """Generates a short, encouraging narrative for a health journey stage."""
        prompt = f"""
        You are an AI health coach. Based on the following user data and projection, write a short, encouraging, and forward-looking narrative (2-3 sentences).
        Focus on the positive changes and milestones for this specific stage of their journey. Use an encouraging and slightly informal tone.

        User & Projection Data:
        {state['journey_data']}

        Example Output:
        "Looking great! By this point, you'll likely start noticing your clothes fitting better and your energy levels improving. Keep up the fantastic momentum!"

        Generate the narrative now.
        """
        response = llm.complete(prompt)
        state["narrative"] = str(response)
        return state

    graph = StateGraph(JourneyState)
    graph.add_node("generate_narrative", generate_narrative)
    graph.add_edge(START, "generate_narrative")
    graph.add_edge("generate_narrative", END)
    return graph.compile()


def load_css(file_name):
    """Loads a CSS file into the Streamlit app."""
    try:
        with open(file_name) as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    except FileNotFoundError:
        st.warning(f"CSS file not found: {file_name}. Glassmorphism will not be applied.")


# --- Helper Functions & Visualization ---
def lbs_to_kg(lbs: float) -> float:
    """Converts pounds to kilograms."""
    return lbs * 0.453592


def ft_in_to_m(feet: float, inches: float) -> float:
    """Converts feet and inches to meters."""
    return (feet * 12 + inches) * 0.0254


def calculate_future_state(current_weight_kg: float, daily_calories: float, tdee: float, days_in_future: int, height_m: float) -> dict:
    """Calculates projected weight and BMI for a future date."""
    calorie_diff = daily_calories - tdee
    weight_change_per_day = calorie_diff / 7700  # Approx. 7700 kcal per kg
    
    projected_weight = current_weight_kg + (days_in_future * weight_change_per_day)
    projected_bmi = projected_weight / (height_m**2) if height_m > 0 else 0
    
    return {"weight": round(projected_weight, 1), "bmi": round(projected_bmi, 1)}


def calculate_tdee(weight_kg: float, height_cm: float, age: int, sex: str, activity_level: str) -> float:
    """Calculates Total Daily Energy Expenditure (TDEE)."""
    # Mifflin-St Jeor Equation for BMR
    if sex == "Male":
        bmr = 10 * weight_kg + 6.25 * height_cm - 5 * age + 5
    else:  # Female
        bmr = 10 * weight_kg + 6.25 * height_cm - 5 * age - 161

    activity_multipliers = {
        "Sedentary (office job)": 1.2,
        "Lightly Active (1-2 days/week)": 1.375,
        "Moderately Active (3-5 days/week)": 1.55,
        "Very Active (6-7 days/week)": 1.725,
        "Extremely Active (physical job/daily training)": 1.9,
    }
    multiplier = activity_multipliers.get(activity_level, 1.2)
    return bmr * multiplier


def get_calorie_target(tdee: float, goal: str) -> float:
    """Calculates the daily calorie target based on the user's goal."""
    if goal == "Lose Weight":
        return tdee - 500
    elif goal == "Gain Weight":
        return tdee + 500
    else:  # Maintain Weight
        return tdee


def create_projection_chart(current_weight: float, daily_calories: float, tdee: float) -> go.Figure:
    """Creates a weight projection chart for the next 90 days."""
    days = list(range(91))
    calorie_diff = daily_calories - tdee
    # Approx. 7700 kcal deficit/surplus to lose/gain 1 kg
    weight_change_per_day = calorie_diff / 7700

    projected_weights = [current_weight + (day * weight_change_per_day) for day in days]
    
    df = pd.DataFrame({
        'Day': days,
        'Projected Weight (kg)': projected_weights
    })

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df['Day'], y=df['Projected Weight (kg)'], mode='lines', name='Projected Weight', line=dict(color='#2ecc71', width=4)))
    fig.update_layout(title="90-Day Weight Projection", xaxis_title="Days from Today", yaxis_title="Weight (kg)", template="plotly_white", height=300)
    return fig


def create_bmi_gauge(bmi: float, category: str) -> go.Figure:
    """Creates a Plotly gauge chart for the BMI value."""
    if category == "Underweight":
        color = "#3498db"  # Blue
    elif category == "Normal":
        color = "#2ecc71"  # Green
    elif category == "Overweight":
        color = "#f1c40f"  # Yellow
    else:  # Obese
        color = "#e74c3c"  # Red

    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=bmi,
            title={"text": f"<b>Category: {category}</b>", "font": {"size": 20}},
            number={"font": {"size": 48}},
            gauge={
                "axis": {"range": [10, 40], "tickwidth": 1, "tickcolor": "darkblue"},
                "bar": {"color": color, "thickness": 0.3},
                "bgcolor": "white",
                "borderwidth": 2,
                "bordercolor": "gray",
                "steps": [
                    {"range": [10, 18.5], "color": "#3498db"},
                    {"range": [18.5, 25], "color": "#2ecc71"},
                    {"range": [25, 30], "color": "#f1c40f"},
                    {"range": [30, 40], "color": "#e74c3c"},
                ],
                "threshold": {
                    "line": {"color": "red", "width": 4},
                    "thickness": 0.75,
                    "value": bmi,
                },
            },
        )
    )
    fig.update_layout(
        height=300,
        margin=dict(l=20, r=20, t=50, b=20),
        font={"color": "#333333", "family": "Arial, sans-serif"},
    )
    return fig


# --- Streamlit Application ---
def main():
    st.set_page_config(page_title="BMI and Health Assistant", layout="wide")

    # Construct an absolute path to the CSS file to ensure it's always found
    script_dir = os.path.dirname(os.path.abspath(__file__))
    css_file_path = os.path.join(script_dir, "style.css")
    load_css(css_file_path)
    st.title("AI Health Twin Dashboard 🧬")

    # --- Workflows ---
    bmi_workflow = get_bmi_workflow()
    insights_workflow = get_insights_workflow()
    journey_workflow = get_journey_insight_workflow()

    # --- Sidebar for User Inputs ---
    with st.sidebar:
        st.header("Your Health Profile")
        
        # Personal Info
        age = st.slider("Age", 18, 100, 30)
        sex = st.selectbox("Sex", ["Male", "Female"])
        
        # Unit selection
        weight_unit = st.selectbox("Weight Unit", ["kg", "lbs"])
        height_unit = st.selectbox("Height Unit", ["cm", "ft/in"])

        # Weight and Height Inputs
        if weight_unit == "kg":
            weight = st.slider("Weight (kg)", 40.0, 150.0, 70.0, 0.5)
        else:
            weight = st.slider("Weight (lbs)", 88.0, 330.0, 154.0, 1.0)

        if height_unit == "cm":
            height_cm_input = st.slider("Height (cm)", 120.0, 220.0, 175.0, 1.0)
        else:
            h_ft = st.number_input("Height (ft)", min_value=4, max_value=7, value=5)
            h_in = st.number_input("Height (in)", min_value=0, max_value=11, value=9)

        # Lifestyle Inputs
        st.divider()
        st.header("Lifestyle & Goals")
        activity_level = st.selectbox("Activity Level", [
            "Sedentary (office job)", "Lightly Active (1-2 days/week)", "Moderately Active (3-5 days/week)", 
            "Very Active (6-7 days/week)", "Extremely Active (physical job/daily training)"
        ])
        daily_calories = st.slider("Daily Calorie Intake", 1000, 4000, 2000, 50)
        goal = st.selectbox("Your Goal", ["Lose Weight", "Maintain Weight", "Gain Weight"])

    # --- Data Processing ---
    weight_kg = lbs_to_kg(weight) if weight_unit == 'lbs' else weight
    if height_unit == 'cm':
        height_m = height_cm_input / 100
        height_cm = height_cm_input
    else:
        height_m = ft_in_to_m(h_ft, h_in)
        height_cm = height_m * 100

    # --- Calculations ---
    if height_m > 0:
        # BMI Calculation
        bmi_state = bmi_workflow.invoke({"weight_kg": weight_kg, "height_m": height_m, "height_cm": height_cm})
        bmi = bmi_state["bmi"]
        bmi_category = bmi_state["category"]

        # TDEE and Calorie Target
        tdee = calculate_tdee(weight_kg, height_cm, age, sex, activity_level)
        calorie_target = get_calorie_target(tdee, goal)

        # Other Metrics
        water_target_l = (weight_kg * 35) / 1000
        protein_target_g = weight_kg * (1.6 if "Active" in activity_level else 0.8)

        # --- Main Dashboard Layout ---
        top_row1, top_row2, top_row3 = st.columns(3)
        with top_row1:
            st.plotly_chart(create_bmi_gauge(bmi, bmi_category), use_container_width=True)
        
        with top_row2:
            st.metric("Daily Calorie Target", f"{int(calorie_target)} kcal")
            st.metric("Your Daily Intake", f"{daily_calories} kcal")
            delta_calories = daily_calories - calorie_target
            st.metric("Surplus/Deficit", f"{int(delta_calories)} kcal", delta=f"{int(delta_calories)} kcal", delta_color="inverse")

        with top_row3:
            st.metric("💧 Water Intake", f"{water_target_l:.1f} L / day")
            st.metric("💪 Protein Intake", f"{int(protein_target_g)} g / day")
            st.metric("🚶 Walking Goal", "10,000 steps")

        st.divider()

        # --- Projections and Insights ---
        mid_col1, mid_col2 = st.columns([0.6, 0.4])

        with mid_col1:
            projection_fig = create_projection_chart(weight_kg, daily_calories, tdee)
            st.plotly_chart(projection_fig, use_container_width=True)

        with mid_col2:
            st.subheader("AI Insights ✨")
            user_data_summary = (
                f"Age: {age}, Sex: {sex}, Weight: {weight_kg:.1f} kg, Height: {height_cm:.1f} cm, BMI: {bmi} ({bmi_category}), "
                f"Activity: {activity_level}, Goal: {goal}, "
                f"Current Intake: {daily_calories} kcal, Target Intake: {int(calorie_target)} kcal."
            )
            with st.spinner("Generating your personalized insights..."):
                insight_state = insights_workflow.invoke({"user_data": user_data_summary})
                st.markdown(insight_state["insight"])

    else:
        st.error("Please set a valid height in the sidebar.")

    # --- Health Journey Timeline ---
    if height_m > 0:
        st.divider()
        st.header("Your Health Journey Timeline 🗺️")
        st.write("Scroll to see your projected progress and AI-powered tips for each stage.")

        journey_stages = {
            "Today": {"days": 0, "icon": "📍"},
            "In 30 Days": {"days": 30, "icon": "🌱"},
            "In 90 Days": {"days": 90, "icon": "🏃‍♂️"},
            "In 6 Months": {"days": 180, "icon": "🏆"},
            "In 1 Year": {"days": 365, "icon": "🌟"},
        }

        weight_goal_kg = 65 # Example goal, can be made dynamic
        initial_weight_diff = abs(weight_kg - weight_goal_kg)

        for stage, data in journey_stages.items():
            future_state = calculate_future_state(weight_kg, daily_calories, tdee, data["days"], height_m)
            
            # Progress bar calculation
            current_weight_diff = abs(future_state["weight"] - weight_goal_kg)
            progress = 0
            if initial_weight_diff > 0:
                progress = max(0, 1 - (current_weight_diff / initial_weight_diff))

            # AI Narrative
            journey_data_summary = (
                f"Stage: {stage}. Current Weight: {weight_kg:.1f}kg. Goal: {goal}. "
                f"Projected Weight: {future_state['weight']}kg. Projected BMI: {future_state['bmi']}. "
                f"Daily calories: {daily_calories}kcal vs Target: {int(calorie_target)}kcal."
            )
            narrative_state = journey_workflow.invoke({"journey_data": journey_data_summary})
            
            # Use markdown with a custom class for CSS animation
            st.markdown(f'<div class="timeline-card">', unsafe_allow_html=True)
            st.subheader(f"{data['icon']} {stage}")
            
            col1, col2 = st.columns(2)
            col1.metric("Projected Weight", f"{future_state['weight']} kg", f"{future_state['weight'] - weight_kg:+.1f} kg")
            col2.metric("Projected BMI", f"{future_state['bmi']}", f"{future_state['bmi'] - bmi:+.1f}")
            
            st.progress(int(progress * 100), text=f"{int(progress*100)}% towards goal")
            st.markdown(f"**AI Coach:** {narrative_state['narrative']}")
            st.markdown('</div>', unsafe_allow_html=True)

    # --- Retain the original Q&A functionality at the bottom ---
    st.divider()
    with st.expander("Have a specific health question? Ask our Q&A bot!"):
        q_col1, q_col2 = st.columns([0.8, 0.2])
        question = q_col1.text_area("Your Question:", "What are some hints for an overweight person?", height=100, label_visibility="collapsed")
        if q_col2.button("Get Answer", use_container_width=True):
            with st.spinner("Thinking..."):
                qa_workflow = get_llm_workflow()
                initial_state = {"question": question}
                final_state = qa_workflow.invoke(initial_state)
                st.markdown(final_state["answer"])


if __name__ == "__main__":
    main()
