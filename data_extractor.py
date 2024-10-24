# data_extractor.py
import openai
from openai import OpenAI
from config import OPENAI_API_KEY  # Import the API key
client = OpenAI(api_key=OPENAI_API_KEY)
from datetime import datetime
import re
import json
import logging
import threading

# Set the OpenAI API key

# Initialize a lock for thread-safe file writing
file_lock = threading.Lock()

def extract_cv_data(text):
    """
    Uses the OpenAI API to extract structured data from the CV text.
    """
    try:
        # First API call for basic information
        data_basic = extract_basic_info(text)

        # Second API call for experience and education
        data_experience = extract_experience_education(text)

        # Combine the results
        data = {**data_basic, **data_experience}
        return data

    except json.JSONDecodeError as json_error:
        logging.error(f"JSON decoding failed: {json_error}")
        logging.error(f"Response text was: {json_error.doc}")
        raise ValueError("Failed to decode JSON from OpenAI response.")
    except Exception as e:
        logging.error(f"An error occurred: {e}")
        raise

def extract_basic_info(text):
    """
    Extracts basic information from the CV text.
    """
    prompt_basic = f"""
You are an AI assistant that extracts specific information from resumes.

Extract the following information from the CV text provided and return it in valid JSON format:

- Applicant's Name
- Role (current or desired)
- Security Clearance (if any)
- Summary (a brief personal statement)
- Skills

Instructions:

- Output only the JSON object, without any markdown formatting or additional text.
- Do not include any code block syntax, such as backticks, explanations, or apologies.
- Ensure the JSON is complete, valid, and parsable by standard JSON parsers.
- Use double quotes for all keys and string values.
- The response should start with a curly brace "{" and end with a curly brace "}".
- Avoid using backticks in your response.

CV Text:
{text}
"""

    response_text = call_openai_api(prompt_basic, max_tokens=1500, call_type="Basic Info Extraction")
    data_basic = parse_json_response(response_text)
    return data_basic

def extract_experience_education(text):
    """
    Extracts experience and education information from the CV text.
    """
    prompt_experience = f"""
You are an AI assistant that extracts specific information from resumes.

Extract the following information from the CV text provided and return it in valid JSON format:

- Experience (as a list of work experiences, each with:
    - "Position"
    - "Company"
    - "Duration"
    - "Responsibilities"
    - "Technologies Used"
  )

- Education (as a list of educational qualifications, each with:
    - "Degree"
    - "Institution"
  )

Instructions:

- Do not include the role location in any of the fields.
- Do not include the education location beyond the name of university or institute.
- Do not mention if the role was a contract position.
- Do not mention the dates of education.
- Focus on the candidate's responsibilities, achievements, and technologies used.
- Output only the JSON object, without any markdown formatting or additional text.
- Do not include any code block syntax, such as backticks, explanations, or apologies.
- Ensure the JSON is complete, valid, and parsable by standard JSON parsers.
- Use double quotes for all keys and string values.
- The response should start with a curly brace "{" and end with a curly brace "}".
- Avoid using backticks in your response.
- Avoid using the American spelling of words, proiritise English spelling.

CV Text:
{text}
"""

    response_text = call_openai_api(prompt_experience, max_tokens=3000, call_type="Experience & Education Extraction")
    data_experience = parse_json_response(response_text)
    return data_experience

def call_openai_api(prompt, max_tokens, call_type=""):
    """
    Calls the OpenAI API with the given prompt and returns the assistant's response text.
    
    Parameters:
    - prompt (str): The prompt to send to the OpenAI API.
    - max_tokens (int): The maximum number of tokens to generate.
    - call_type (str): An optional identifier for the type of call (e.g., 'Basic Info', 'Experience').
    """
    try:
        response = client.chat.completions.create(model="gpt-4o-mini",  # Use your valid model name
        messages=[
            {"role": "user", "content": prompt}
        ],
        max_tokens=max_tokens,
        temperature=0)

        response_text = response.choices[0].message.content.strip()
        logging.debug(f"Assistant's raw response:\n{response_text}\n")

        # Get current timestamp
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Prepare the log entry
        if call_type:
            log_entry = f"\n\n=== {call_type} === [{timestamp}]\n{response_text}"
        else:
            log_entry = f"\n\n=== {timestamp} ===\n{response_text}"

        # Acquire the lock before writing to the file
        with file_lock:
            with open("assistant_response.txt", "a", encoding="utf-8") as f:
                f.write(log_entry)

        # Remove any backticks from the response
        response_text = response_text.replace('`', '')

        return response_text

    except openai.RateLimitError as e:
        logging.error(f"Rate limit exceeded: {e}")
        raise
    except openai.InvalidRequestError as e:
        logging.error(f"Invalid request: {e}")
        raise
    except openai.AuthenticationError as e:
        logging.error(f"Authentication error: {e}")
        raise
    except openai.OpenAIError as e:
        logging.error(f"OpenAI API error: {e}")
        raise

def parse_json_response(response_text):
    """
    Parses the assistant's response text as JSON.
    """
    try:
        data = json.loads(response_text)
        return data
    except json.JSONDecodeError:
        # Attempt to extract JSON using regex
        json_str = extract_json(response_text)
        try:
            data = json.loads(json_str)
            return data
        except json.JSONDecodeError as e:
            logging.error(f"JSON decoding failed: {e}")
            logging.error(f"Problematic JSON string: {json_str}")
            raise

def extract_json(text):
    """
    Extracts the JSON object from the text using a regular expression.
    """
    # This regex matches the first JSON object in the text
    match = re.search(r'\{(?:[^{}]|(?R))*\}', text, re.DOTALL)
    if match:
        return match.group(0)
    else:
        logging.error("No JSON object found in the assistant's response.")
        raise ValueError("No JSON object found in the assistant's response.")
