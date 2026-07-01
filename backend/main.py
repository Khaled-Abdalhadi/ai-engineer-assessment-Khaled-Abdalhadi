from fastapi import FastAPI, Body, HTTPException, Request
from fastapi.responses import PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from typing import Annotated
from google import genai
from google.genai import types, errors
from google.genai._gaos.lib.compat_errors import AuthenticationError
import requests
import json

gemini_api_key = "AQ.Ab8RN6LAKgtQGpg5JTQ4ogBk3JI_p8TAUY1iIZUnVGgkMK5tgA"
token = "3779984fa6a1dcc9471edd030d658461"
superhero_base_url = f"https://superheroapi.com/api/{token}"


app = FastAPI()

client = genai.Client(api_key= gemini_api_key)

#later on for safety reasons only allow requests from trusted sources and also add credentials
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)

#open the world cup csv file and read it in bytes
with open("world_cup.csv", "rb") as f:
    world_cup_bytes = f.read()
    
#prompt engineering of the system prompt (configuring the model)
system_prompt = """
You are an assistant that is only supposed to answer questions based on either the fifa world cup or superheros.

Rules:
- Do not answer any opinionated questions such as who is your favorite superhero or who is your favorite world cup team.
- Only call get_worldcup if the user explicitly mentions "world cup" or FIFA World Cup.
_ Do not call get_worldcup if the user prompt asks about countries in general or dates in general.
- Only call get_superhero when the user asks about superheros.
"""

#gemini LLM will call this function if user prompt asks about a superhero
superhero_function = {
    "type": "function",
    "name": "get_superhero",
    "description": "extracts the name of the superhero from the user prompt. Calls the superhero api and return back information relevant to the extracted superhero name",
    "parameters": {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "The name of the superhero, e.g. spiderman",
            }
        },
        "required": ["name"],
    }
}

#gemini LLM will call this function if user prompt is related to the world cup
worldcup_function = {
    "type": "function",
    "name": "get_worldcup",
    "description": "makes a LLM call that analysis a world cup csv file and return a summary relevant to the user prompt.",
    "parameters": {
        "type": "object",
        "properties": {
            "user_prompt": {
                "type": "string",
                "description": "the query of what the user is looking for in the csv file"
            }
        }
    }
}

#calls the SuperHero API and retrieves information about the superhero to query for
def get_superhero(name):
    
    url = f"{superhero_base_url}/search/{name}"
    
    #error handling
    try:
        response = requests.request("GET", url)
      
        #for simplicity: only return the first result (later on can print more results if required)
        superhero_data = json.dumps(json.loads(response.text)["results"][0])

        #make another call to gemini to summarize the superhero data returned from the API
        user_prompt = f"""
            Here is JSON data for a comic book character:
            
            {superhero_data}
            
            Create a short engaging biography that includes his name, physical traits, where he was born and data you find relevant in the input data.
            
            Return ONLY valid JSON with:
            -summary: string (2-4 sentences)
            -image_url: string (must come from input data)
        """
        
        response = client.models.generate_content(
            model="gemini-3.1-flash-lite",
            contents=user_prompt,
            config = types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema={
                    "type": "object",
                    "properties": {
                        "summary": {"type": "string"},
                        "image_url": {"type": "string"}
                    },
                    "required": ["summary", "image_url"]
                }
            )
        )
        
        return response.text
    except:
        return f"I am sorry but I could not find any information about {name}  \U0001F615"
 

#requests gemini LLM to read the world_cup.csv file and returns a summary of the response based on the user prompt
def get_worldcup(user_prompt):
    
    csv_response = client.models.generate_content(
        model = "gemini-3.1-flash-lite",
        config= {
            "system_instruction": "respond only in text. Summarize the output into a paragraph."
        },
        contents = [
            types.Part.from_bytes(
                data=world_cup_bytes,
                mime_type="text/csv",
            ),
            user_prompt,
        ]
    )
    
    return csv_response.text

#a customized request validation error handler to just send back a string of the error message
@app.exception_handler(RequestValidationError)
async def invalid_user_prompt_exception_handler(request: Request, error: RequestValidationError):
    return PlainTextResponse(content = "Invalid user prompt, only strings are allowed!", status_code=422)

#a customized http exception handler to only return plain text
@app.exception_handler(HTTPException)
async def http_custom_exception_handler(request: Request, error: HTTPException):
    return PlainTextResponse(content= error.detail, status_code=error.status_code)
    

@app.post("/ask")
def call_gemini(user_prompt: Annotated[str, Body()]):
    try:
        #make a call to gemini LLM
        response = client.interactions.create(
        model = "gemini-3.1-flash-lite",
        system_instruction = system_prompt,
        input= user_prompt,
        tools = [superhero_function, worldcup_function]
        )
        print(response.status)

        #based on the user prompt, trigger the proper function call
        for step in response.steps:
            match step.type:
                case "model_output":
                    return "I am sorry but i can only answer questions related to superheros or the fifa world cup!  \U0001F92D"
                
                case "function_call":
                    
                    if(step.name == "get_superhero"):
                        print(step.arguments)
                        response = get_superhero(**step.arguments)
                    
                        return {
                            "name": step.arguments["name"],
                            "message": response,
                            "source": "superhero API",
                            "source_url": "https://superheroapi.com/"
                        }
                    
                    elif(step.name == "get_worldcup"):
                        response = get_worldcup(**step.arguments)

                        return {
                            "message": response,
                            "source": "Football - FIFA World Cup, 1930 - 2026",
                            "source_url": "https://www.kaggle.com/datasets/piterfm/fifa-football-world-cup?resource=download&select=world_cup.csv"
                        }
    
    #add specific gemini error handling here later                    
    except errors.APIError as e:
        print("GenAI API error occured!")
        
    #if gemini failed to catch error or if we have general error
    except Exception as e:
        
        ##identify the error
        print(e)
        
        #error triggered when gemini authentication fails (not sure why i cant use it in the above exception)
        if isinstance(e, AuthenticationError):
            raise HTTPException(status_code = 401, detail = f"Gemini API Error: {e.body[0]["error"]["message"]}")
        
        
            
    

#TO DO LIST: 
# 1. create a post endpoint
# 2. create a very simple front end
# 3. host it on azure
# 4. add catch errors for all api calls
# 5. restrict the llm to only a fixed amount of token. Anything creater than that should return an error
# 6. add rate limiting to only send specific number of requests to the model in a fixed period of time