import os  
import requests  
  
class GPTWrapperError(Exception):  
    pass  
  
class GPTWrapper:  
  
    def __init__(self, azure_key_path=None, endpoint=None):  

        if azure_key_path is not None:
            with open(azure_key_path, "r") as key_file:
                self.api_key = key_file.read().strip()
        else:
            # load key from env vars:
            self.api_key = os.getenv("AZURE_API_KEY")

        if endpoint is None:
            self.azure_endpoint = os.getenv("AZURE_ENDPOINT")
        else:
            self.azure_endpoint = endpoint
        
        self.headers = {  
            "Content-Type": "application/json",  
            "api-key": self.api_key,  
        }  
  
    def send_request(self, messages, model="gpt-35-turbo", temperature=0.7, max_tokens=800, top_p=0.95, frequency_penalty=0, presence_penalty=0, stop=None):  
        payload = {  
            "model": model,  
            "messages": messages,  
            "temperature": temperature,  
            "max_tokens": max_tokens,  
            "top_p": top_p,  
            "frequency_penalty": frequency_penalty,  
            "presence_penalty": presence_penalty,  
            "stop": stop,  
        }  
  
        try:  
            response = requests.post(self.azure_endpoint, headers=self.headers, json=payload)  
            response.raise_for_status()  
        except requests.RequestException as e:  
            raise GPTWrapperError(f"Failed to send the request. Error: {e}")  
  
        return response  
  
    def process_text(self, system_prompt, user_question, model="gpt-35-turbo", max_tokens=800, temperature=0.7, top_p=0.95, frequency_penalty=0, presence_penalty=0, stop=None):  
        messages = [  
            {"role": "system", "content": system_prompt},  
            {"role": "user", "content": user_question},  
        ]  
  
        response = self.send_request(messages, model, max_tokens=max_tokens, temperature=temperature, top_p=top_p, frequency_penalty=frequency_penalty, presence_penalty=presence_penalty, stop=stop)  
        return response  
  
# Main function  
def main():  
    gpt_wrapper = GPTWrapper()  
  
    system_prompt = "You are an AI assistant that helps people find information."  
    user_question = "What is the capital of France?"  
    # model = "gpt-35-turbo"
    model = "GPT4"
    response = gpt_wrapper.process_text(system_prompt, user_question, model, max_tokens=800, temperature=0.7, top_p=0.95, frequency_penalty=0, presence_penalty=0, stop=None)  
      
    print(response.json()['choices'][0]['message']['content'])  
  
# Call main function  
if __name__ == "__main__":  
    main()  
