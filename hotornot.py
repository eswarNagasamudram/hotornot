import vertexai
from vertexai.preview.generative_models import GenerativeModel, Part
from google.oauth2 import service_account
import json
from vertexai.preview.language_models import TextGenerationModel
import promptDict_hon
import promptTypeConstants
import csv
import pandas as pd
from collections import defaultdict
from sklearn.metrics import confusion_matrix
import constants
import openpyxl
import cv2
import base64
import time
from openai import OpenAI
import os
import requests

def get_video_from_file_gemini(file_path):
    file_path = constants.VIDEO_FILE_DIRECTORY_PATH + file_path 
    with open(file_path,"rb") as video_file :
      video_data = video_file.read()
    video_data = Part.from_data(data=video_data, mime_type="video/mp4")
    return video_data

def get_video_from_file_open_ai(file_path):
    video = cv2.VideoCapture(constants.VIDEO_FILE_DIRECTORY_PATH + file_path + ".mp4")
    base64Frames = []
    while video.isOpened():
        success, frame = video.read()
        if not success:
            break
        _, buffer = cv2.imencode(".jpg", frame)
        base64Frames.append(base64.b64encode(buffer).decode("utf-8"))

    video.release()
    print(len(base64Frames), "frames read.")
    return base64Frames

def get_video_from_file(file_path, model):
    if model == constants.GEMINI_MODEL:
        return get_video_from_file_gemini(file_path=file_path)
    else :
        return get_video_from_file_open_ai(file_path=file_path)

def vertex_init():
    credentials = service_account.Credentials.from_service_account_file(filename="vertex-key.json")
    vertexai.init(project = "kyc-gpt", credentials=credentials)

def handleJsonError(json_data) :
    parameters = {
        "max_output_tokens": 2048,
        "temperature": 0,
        "top_p": 1
    }
    model = TextGenerationModel.from_pretrained("text-bison")
    response = model.predict( """You are a JSON correcting AI agent. You will be given input of text which is not a well formed JSON. You will have to generate an output correcting the format errors of the input.

            input: { 
                "category" : "Medium", 
                "gender" : "Female"
                "age" : "25-30"
                "facial_weight" : "Right weight
                "rationale" : "The person is labelled medium because though the person has good facial symmetry, his nose is slightly crooked and no sharp features make him less attractive"
                }
            output: { 
                "category" : "Medium", 
                "gender" : "Female",
                "age" : "25-30",
                "facial_weight" : "Right weight",
                "rationale" : "The person is labelled medium because though the person has good facial symmetry, his nose is slightly crooked and no sharp features make him less attractive"
                }

            input:""" + json_data + "output :", **parameters)
    return response.text

def parse_ai_response(response, promptType : str) :
    
    cleaned_text = response.replace("```json\n", "").replace("```","").replace("```json\n{","").replace("JSON","").replace("\n","").strip()
    try:
        json_data = json.loads(cleaned_text)
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON: {e}")
        cleaned_text = response.strip()
        json_data = handleJsonError(json_data=cleaned_text)
        json_data = json.loads(json_data)
        
    if promptType == promptTypeConstants.PLAIN_PROMPT :
        array_from_json = [
                json_data["category"],
                json_data["gender"],
                json_data["age"],
                json_data["facial_weight"],
                json_data["rationale"],
        ]
    elif promptType == promptTypeConstants.COT :
        array_from_json = [
                json_data["thinking"],
                json_data["category"],
                json_data["gender"],
                json_data["age"],
                json_data["facial_weight"],
                json_data["rationale"],
        ]
    elif promptType == promptTypeConstants.PROMPTCHAIN :
        array_from_json = [
                json_data["symmetry_label"],
                json_data["symmetry_rationale"],
                json_data["age_label"],
                json_data["age_rationale"],
                json_data["features_label"],
                json_data["features_rationale"],
                json_data["weight_label"],
                json_data["weight_rationale"],
                json_data["skin_label"],
                json_data["skin_rationale"],
                json_data["overall_rating"],
        ]
    elif promptType == promptTypeConstants.NEWPROMPT :
        array_from_json = [
            json_data["facial_features"],
            json_data["gender"],
            json_data["age"],
            json_data["facial_weight"],
            json_data["grooming"],
            json_data["others"]
        ]
    return array_from_json

def searialise_category_labels(label:str):
    label = label.strip()
    if label == "High" or label == "high" or label == "h" or label == "H":
        label = "H"
        return label
    elif label == "Medium" or label == "medium" or label == "m" or label == "M":
        label = "M"
        return label
    elif label == "Low" or label == "low" or label == "l" or label == "L":
        label = "L"
        return label
    else :
        return "NA"

def get_prompt_type_from_id(promptId):
    if promptId == 3 or promptId == 4 or promptId == 5 or promptId == 3.1 or promptId == 4.1 or promptId == 5.1 :
        return promptTypeConstants.PLAIN_PROMPT
    if promptId == 3.2 or promptId == 4.2 or promptId == 5.2 :
        return promptTypeConstants.COT
    if promptId == 6 :
        return promptTypeConstants.PROMPTCHAIN
    if promptId == 6.1 :
        return promptTypeConstants.NEWPROMPT
    return promptTypeConstants.PLAIN_PROMPT

def get_df_for_prompt(promptType):
    if promptType == promptTypeConstants.PLAIN_PROMPT:
        colunms = ["file_name", "label", "reasoning", "category","gender","age","facial_weight","rationale"]
    if promptType == promptTypeConstants.COT :
        colunms = ["file_name", "label", "reasoning","thinking","category","gender","age","facial_weight","rationale"]
    if promptType == promptTypeConstants.PROMPTCHAIN:
        colunms = ["file_name", "label", "reasoning", "symmetry_label",
                "symmetry_rationale",
                "age_label",
                "age_rationale",
                "features_label",
                "features_rationale",
                "weight_label",
                "weight_rationale",
                "skin_label",
                "skin_rationale",
                "overall_rating"]
    if promptType == promptTypeConstants.NEWPROMPT:
        colunms = ["file_name", "label", "reasoning","facial_features", "gender", "age", "facial_weight", "grooming", "others"]
    df = pd.DataFrame(columns = colunms)
    return df

def get_default_json(promptId):
    promptType = get_prompt_type_from_id(promptId)
    if promptType == promptTypeConstants.PLAIN_PROMPT:
        return """{ 
                    "category" : "NA", 
                    "gender" : "NA"
                    "age" : "NA"
                    "facial_weight" : "NA"
                    "rationale" : "NA"
                    } """
    if promptType == promptTypeConstants.COT:
        return """{ 
                    "thinking" :"NA"
                    "category" : "NA", 
                    "gender" : "NA"
                    "age" : "NA"
                    "facial_weight" : "NA"
                    "rationale" : "NA"
                    } """
    if promptType == promptTypeConstants.PROMPTCHAIN:
        return """{
                    "symmetry_label" : "NA",
                    "symmetry_rationale" : "NA",
                    "age_label" : "NA",
                    "age_rationale" : "NA",
                    "features_label" : "NA",
                    "features_rationale" : "NA",
                    "weight_label" : "NA",
                    "weight_rationale" : "NA",
                    "skin_label" : "NA",
                    "skin_rationale" : "NA"
                    "overall_rating" : "NA"
                    } """
    if promptType == promptTypeConstants.NEWPROMPT:
        return """{
                    "facial_features": "H",
                    "gender": "M",
                    "age": "35-40",
                    "facial_weight": "M",
                    "grooming": "M",
                    "others": "thick eyebrows, black hair"
                    }"""
    return """{ 
                    "category" : "NA", 
                    "gender" : "NA"
                    "age" : "NA"
                    "facial_weight" : "NA"
                    "rationale" : "NA"
                    } """

def generate_response_open_ai(prompt:str, video, promptId, client):
    PROMPT_MESSAGES = [
    {
        "role": "user",
        "content": [
            {"type" : "text", "text" : prompt},
            {"type" : "image_url", "image_url" : {"url" : f"data:image/jpeg;base64,{video[3]}"}},
            {"type" : "image_url", "image_url" : {"url" : f"data:image/jpeg;base64,{video[4]}"}},
            {"type" : "image_url", "image_url" : {"url" : f"data:image/jpeg;base64,{video[5]}"}},
            {"type" : "text", "text" : "Reply in JSON output only. Incase of error,make a full report of the cause of any issues in receiving, understanding, or describing images.Output :"},
        ],
    }
        ]
    params = {
        "model": "gpt-4-vision-preview",
        "messages": PROMPT_MESSAGES,
        "max_tokens": 2048,
    }
    result = None
    try:
        result = client.chat.completions.create(**params)
    except Exception as e :
        print(f"Some issue occured in generating response {e}. Trying again")
        try:
            result = client.chat.completions.create(**params)
        except Exception as e:
            print(f"Retrying also failed with exceptioin {e}. Moving on")
            return get_default_json(promptId=promptId)
        
    return result.choices[0].message.content
    


def generate_responses_gemini(prompt : str, video, promptId):
    model = GenerativeModel("gemini-pro-vision")
    generation_config={
          "max_output_tokens": 2048,
          "temperature": 0,
          "top_p": 1,
          "top_k": 32
      }
    try:
        response = model.generate_content([prompt, video,"output :"], generation_config=generation_config)
    except Exception as e :
        print(f"Some issue occured in generating response {e}. Trying again")
        try :
            response = model.generate_content([prompt, video,"output :"], generation_config=generation_config)
        except Exception as e :
            print(f"Retrying also failed with exceptioin {e}. Moving on")
            return get_default_json(promptId=promptId)
    return response.candidates[0].content.parts[0].text

def generate_response(prompt, video, promptId, model, client):
    if model == constants.GEMINI_MODEL:
        return generate_responses_gemini(prompt= prompt, video=video, promptId=promptId)
    else :
        return generate_response_open_ai(prompt=prompt, video=video, promptId=promptId, client = client)

def read_input_data(file_path):
    data = []
    with open(file_path, 'r', newline='') as file:
        csv_reader = csv.DictReader(file)
        for row in csv_reader:
            file_name = row['file_name']
            label = row['label']
            reasoning = row['reasoning']
            data.append((file_name, label, reasoning))
    return data

def get_model_label(response_array,promptId ):
    promptType = get_prompt_type_from_id(promptId=promptId)
    if promptType == promptTypeConstants.PLAIN_PROMPT:
        return response_array[0]
    if promptType == promptTypeConstants.COT:
        return response_array[1]
    if promptType == promptTypeConstants.PROMPTCHAIN:
        return response_array[10]
    if promptType == promptTypeConstants.NEWPROMPT:
        return response_array[0]

def serialise_response_array(response_array, promptId):
    promptType = get_prompt_type_from_id(promptId=promptId)
    if promptType == promptTypeConstants.PLAIN_PROMPT:
        response_array[0] = searialise_category_labels(response_array[0])
        return response_array
    if promptType == promptTypeConstants.COT:
        response_array[1] = searialise_category_labels(response_array[1])
        return response_array
    if promptType == promptTypeConstants.PROMPTCHAIN:
        response_array[10] = searialise_category_labels(response_array[10])
        return response_array
    return response_array
def generate_and_save_predictions(data, output_file, promptId, model:str, client:None) :
    predictions = []
    actual_labels = []
    model_labels = []
    
    df = get_df_for_prompt(get_prompt_type_from_id(promptId=promptId))
    for file_name, label, reasoning in data :
        
        video_data = get_video_from_file(file_name, model)
        prompt = promptDict_hon.get_prompt(prompt_id=promptId)
        model_response = generate_response(prompt=prompt, video=video_data, promptId=promptId, model =model, client = client)
        print(model_response)
        response_array = parse_ai_response(model_response, promptType= get_prompt_type_from_id(promptId=promptId))
        response_array = serialise_response_array(response_array=response_array,promptId=promptId)

        output_array = [file_name,label,reasoning] + response_array
        print(output_array)
        predictions.append(output_array)
        df.loc[len(df)] = output_array
        
        actual_labels.append(label)
        model_label = get_model_label(response_array,promptId)
        model_label = searialise_category_labels(model_label)
        model_labels.append(model_label)
    
    
    with pd.ExcelWriter(output_file, mode='a', engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name="SHEET-"+str(promptId), index=False)

    # Print confusion matrix
    cm = confusion_matrix(actual_labels, model_labels)
    print(f"\nConfusion Matrix for PROMPT - {promptId}:")
    print(cm)

    # Print summary
    correct_predictions = sum(actual == predicted for actual, predicted in zip(actual_labels, model_labels))
    total_predictions = len(actual_labels)
    accuracy = correct_predictions / total_predictions * 100
    print(f"\nSummary for PROMPT - {promptId}:")
    print(f"Total predictions: {total_predictions}")
    print(f"Correct predictions: {correct_predictions}")
    print(f"Accuracy: {accuracy:.2f}%")

def main():
    print("Starting the process \n")
    
    # initialise google vertex
    vertex_init()

    # initialise openAI
    client = OpenAI(api_key=constants.OPENAI_API_KEY)

    input_data = read_input_data("input2.csv")
    output_file_name = "run_output_new_dataset.xlsx"

    #Generating results for promptId - 3 | Model - Gemini
    # generate_and_save_predictions(input_data,output_file_name,3,constants.GEMINI_MODEL, client=client)

    # #Generating results for promptId - 3.1 | Model - Gemini
    # generate_and_save_predictions(input_data,output_file_name,3.1,constants.GEMINI_MODEL, client=client)

    # #Generating results for promptId - 3.2 | Model - Gemini
    # generate_and_save_predictions(input_data,output_file_name,3.2,constants.GEMINI_MODEL, client=client)

    # #Generating results for promptId - 4 | Model - Gemini
    # generate_and_save_predictions(input_data,output_file_name,4,constants.GEMINI_MODEL, client=client)

    # #Generating results for promptId - 4.1 | Model - Gemini
    # generate_and_save_predictions(input_data,output_file_name,4.1,constants.GEMINI_MODEL, client=client)

    # #Generating results for promptId - 4.2 | Model - Gemini
    # generate_and_save_predictions(input_data,output_file_name,4.2,constants.GEMINI_MODEL, client=client)

    # #Generating results for promptId - 5 | Model - Gemini
    # generate_and_save_predictions(input_data,output_file_name,5,constants.GEMINI_MODEL, client=client)

    #Generating results for promptId - 5.1 | Model - Gemini
    # generate_and_save_predictions(input_data,output_file_name,5.1,constants.GEMINI_MODEL, client=client)

    #Generating results for promptId - 5.2 | Model - Gemini
    # generate_and_save_predictions(input_data,output_file_name,5.3,constants.GEMINI_MODEL, client=client)

    # #Generating results for promptId - 6 | Model - Gemini
    generate_and_save_predictions(input_data,output_file_name,6.1,constants.GEMINI_MODEL, client=client)

    
if __name__ == "__main__" :
    main()