import sys
import re
from openai import OpenAI
from zhipuai import ZhipuAI
from agent import *
from utils_mobile.and_controller import AndroidController, list_all_devices
from utils_mobile.utils import print_with_color


def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')


def get_code_snippet(content):
    code = re.search(r'```.*?([\s\S]+?)```', content)
    if code is None:
        return content
        # print(content)
        # raise RuntimeError("No available code found!")
    code = code.group(1).strip()
    code = code.split("\n")[-1]

    return code


def handle_backoff(details):
    print(f"Retry {details['tries']} for Exception: {details['exception']}")


def handle_giveup(details):
    print(
        "Backing off {wait:0.1f} seconds afters {tries} tries calling fzunction {target} with args {args} and kwargs {kwargs}"
        .format(**details))


def detect_answer(question: str, model_answer: str, standard_answer: str, args):
    # print(f"Question: {question}\nModel Answer: {model_answer}\nStandard Answer: {standard_answer}")
    detect_prompt = f"You need to judge the model answer is True or False based on Standard Answer we provided. You should whether answer [True] or [False]. \n\nQuestion: {question}\n\nModel Answer: {model_answer}\n\nStandard Answer: {standard_answer}"
    call_time = 0
    while call_time <= 5:
        call_time += 1
        if args.judge_model == "glm4":
            return_message = get_completion_glm(prompt=detect_prompt, glm4_key=args.api_key)
        elif "gpt" in args.judge_model:
            # print(f"api_key: {args.api_key}, api_url: {args.api_base}")
            return_message = get_completion_gpt(prompt=detect_prompt, model_name = args.judge_model, api_key=args.api_key, api_url=args.api_base)
        if "True" in return_message:
            return True
        elif "False" in return_message:
            return False

def detect_answer_test(args):
    # print(f"Question: {question}\nModel Answer: {model_answer}\nStandard Answer: {standard_answer}")
    detect_prompt = "hello! who are you"
    call_time = 0
    while call_time <= 5:
        call_time += 1
        return_message = None
        if args.judge_model == "glm4":
            return_message = get_completion_glm(prompt=detect_prompt, glm4_key=args.api_key)
        elif "gpt" in args.judge_model:
            return_message = get_completion_gpt(prompt=detect_prompt, model_name = args.judge_model, api_key=args.api_key, api_url=args.api_base)
        else:
            print("ERROR: No model found!")
            sys.exit()
        print("Here is the judge_model test: ")
        print("Question: ", detect_prompt)
        print("Model Answer: ", return_message)
        if not isinstance(return_message, str):
            print("ERROR: Judge model error!")
            sys.exit()
        else:
            return


@backoff.on_exception(backoff.expo,
                      Exception,
                      max_tries=5,
                      on_backoff=handle_backoff, 
                      giveup=handle_giveup)
def get_completion_glm(prompt, glm4_key):
    client = ZhipuAI(api_key=glm4_key)
    response = client.chat.completions.create(
        model="glm-4", 
        messages=[
            {"role": "user", "content": prompt},
        ],
    )
    return response.choices[0].message.content

@backoff.on_exception(backoff.expo,
                      Exception, 
                      max_tries=5,
                      on_backoff=handle_backoff,
                      giveup=handle_giveup)  
def get_completion_gpt(prompt, model_name, api_key, api_url):
    # print(f"api_key: {api_key}, api_url: {api_url}")
    client = OpenAI(api_key=api_key, base_url=api_url)
    messages = [{
            "role": "user",
            "content": prompt
        }]
    # print(f"Request: {messages}")
    r = client.chat.completions.create(
        model=model_name,
        messages=messages,
        max_tokens=512,
        temperature=0.001
    )
    print(f"Response: {r.choices[0].message.content}")
    return r.choices[0].message.content


def get_mobile_device():
    device_list = list_all_devices()
    if not device_list:
        print_with_color("ERROR: No device found!", "red")
        sys.exit()
    print_with_color(f"List of devices attached:\n{str(device_list)}", "yellow")
    if len(device_list) == 1:
        device = device_list[0]
        print_with_color(f"Device selected: {device}", "yellow")
    else:
        print_with_color("Please choose the Android device to start demo by entering its ID:", "blue")
        device = input()

    controller = AndroidController(device)
    width, height = controller.get_device_size()
    if not width and not height:
        print_with_color("ERROR: Invalid device size!", "red")
        sys.exit()
    print_with_color(f"Screen resolution of {device}: {width}x{height}", "yellow")

    return controller


def get_mobile_device_and_name():
    device_list = list_all_devices()
    if not device_list:
        print_with_color("ERROR: No device found!", "red")
        sys.exit()
    print_with_color(f"List of devices attached:\n{str(device_list)}", "yellow")
    if len(device_list) == 1:
        device = device_list[0]
        print_with_color(f"Device selected: {device}", "yellow")
    else:
        print_with_color("Please choose the Android device to start demo by entering its ID:", "blue")
        device = input()

    controller = AndroidController(device)
    width, height = controller.get_device_size()
    if not width and not height:
        print_with_color("ERROR: Invalid device size!", "red")
        sys.exit()
    print_with_color(f"Screen resolution of {device}: {width}x{height}", "yellow")

    return controller, device