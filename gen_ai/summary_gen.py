from dotenv import load_dotenv
import pandas as pd

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic

from index_construction import IndexConstructor
from system_prompt import system_prompt
from models import MODEL_PROVIDERS

load_dotenv()


class RiskSummaryGenerator:
    """
    Generates a financial risk summary using a specified language model.
    """

    def __init__(self, model_name: str, temperature: float = 0.2):
        """
        Initializes the generator with a specific model.

        Args:
            model_name (str): The ticker name of the model to use (e.g., "gpt-4o", "llama3-8b-8192").
            temperature (float): The temperature setting for the model's response generation.
        """
        self.model_name = model_name
        self.temperature = temperature
        self.llm = self._get_llm_instance()

    def _get_llm_instance(self) -> BaseChatModel:
        """
        Selects and instantiates the correct LangChain ChatModel based on the model name.

        Returns:
            An instance of a LangChain chat model (e.g., ChatOpenAI, ChatGroq).

        Raises:
            ValueError: If the model_name is not found in the supported list.
        """
        if self.model_name in MODEL_PROVIDERS["OpenAI"]:
            return ChatOpenAI(model=self.model_name, temperature=self.temperature)

        elif self.model_name in MODEL_PROVIDERS["Anthropic"]:
            return ChatAnthropic(
                model_name=self.model_name,
                temperature=self.temperature,
                timeout=None,
                stop=None,
            )

        elif self.model_name in MODEL_PROVIDERS["Gemini"]:
            return ChatGoogleGenerativeAI(
                model=self.model_name, temperature=self.temperature
            )

        elif self.model_name in MODEL_PROVIDERS["Groq"]:
            return ChatGroq(model_name=self.model_name, temperature=self.temperature)

        else:
            # If the model is not found, raise an error with a helpful message
            all_models = [
                model
                for provider_models in MODEL_PROVIDERS.values()
                for model in provider_models
            ]
            raise ValueError(
                f"Model '{self.model_name}' is not supported. "
                f"Please choose from the following: {all_models}"
            )

    def generate_summary(self, input_data: pd.DataFrame) -> str:
        """
        Generates the risk summary by processing the SRI data through the LLM chain.

        Returns:
            A string containing the generated risk summary.
        """
        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", system_prompt),
                ("human", "{input}"),
            ]
        )

        chain = prompt | self.llm

        if input_data.empty:
            return "Could not generate summary because the input data is empty. Please check the data source."

        input_data_str = input_data.to_markdown()

        response = chain.invoke(
            {
                "input": input_data_str,
            }
        )

        # Ensure the response is always a string
        if isinstance(response.content, str):
            return response.content
        elif isinstance(response.content, list):
            return "\n".join(
                str(item) if isinstance(item, str) else str(item)
                for item in response.content
            )
        else:
            return str(response.content)
