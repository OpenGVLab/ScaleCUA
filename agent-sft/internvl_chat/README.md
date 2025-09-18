# Training Computer Use Agents with InternVL

This repository provides a training framework for computer use agents with InternVL models. 

## Environment
```bash
pip install -r requirements.txt
```

## Download Pretrained Models
Before starting fine-tuning, download the pre-trained model we provide.

```bash
mkdir pretrained/
huggingface-cli download --resume-download --local-dir-use-symlinks False OpenGVLab/InternVL3-8B --local-dir pretrained/InternVL3-8B
```

## Prepare Customized Data
After downloading the pre-trained model, prepare your customized SFT (Supervised Fine-Tuning) data. Update the JSON file in agent-sft/internvl_chat/data/train_meta.json similar to [aaa](bbb)

The format for the JSON file should be:
```json
{
  "your-custom-dataset-1": {
    "root": "path/to/the/image/",
    "annotation": "path/to/the/jsonl/annotation",
    "conv_style": "internvl2_5_mobile_planning_cot_v1",
    "data_augment": false,
    "max_dynamic_patch": 12,
    "repeat_time": 1,
    "length": "number of samples in the dataset"
  }
}
```

The jsonl annotation looks like: 
```json
{"image": "android_lab_data_Cantook/cantook_5/images/home_screen.png", "conversations": [{"from": "human", "value": "<image>\nPlease generate the next move according to the UI screenshot, task and previous operations.\n\nTask: Could you check my reading progress for War and Peace?\n\nPrevious operations:\nNone"}, {"from": "gpt", "value": "<think>\nBased on the second image, I can see this is an e-reader app showing a \"Recently read\" section with several books including \"1984\" by George Orwell (79.5% complete), \"The Sorcerer's Stone\" by J.K. Rowling (48.8% complete), and \"King of Envy\" by Ana Huang (52.9% complete). However, I don't see \"War and Peace\" anywhere in the currently visible book collection, either in the \"Recently read\" or \"Recently added\" sections. I would need to search or browse through the library further to find War and Peace and check its reading progress.\n</think>\n<operation>\nOpen the Cantook app to access your digital book library, which shows recently read books including '1984' by George Orwell (79.5% complete), 'The Sorcerer's Stone' by J.K. Rowling (48.8%), 'King of Envy' by Ana Huang (52.9%), and 'A Christmas Carol'. The app also displays your recently added books including multiple Harry Potter titles.\n</operation>\n<action>\nopen_app(app_name='Cantook')\n</action>"}], "width": 1440, "height": 3120}
{"image": "android_lab_data_Cantook/cantook_5/images/001_start_1749723405576.png", "conversations": [{"from": "human", "value": "<image>\nPlease generate the next move according to the UI screenshot, task and previous operations.\n\nTask: Could you check my reading progress for War and Peace?\n\nPrevious operations:\nStep 1: \"Open the Cantook app to access your digital book library, which shows recently read books including '1984' by George Orwell (79.5% complete), 'The Sorcerer's Stone' by J.K. Rowling (48.8%), 'King of Envy' by Ana Huang (52.9%), and 'A Christmas Carol'. The app also displays your recently added books including multiple Harry Potter titles.\""}, {"from": "gpt", "value": "<think>\nLooking at the screenshot of this e-reader app, I can see the user's library with several books including \"1984\" (79.5% complete), \"The Sorcerer's Stone,\" \"King of Envy,\" \"A Christmas Carol,\" and Harry Potter titles in the \"Recently read\" and \"Recently added\" sections. However, I don't see \"War and Peace\" displayed anywhere in the current Home view. The navigation tabs at the bottom show I could access \"My Books,\" which would likely provide a more complete view of the entire library where I might find War and Peace and check its reading progress. The most logical next step would be to navigate to the \"My Books\" section to search for this specific title.\n</think>\n<operation>\nClick on the 'My Books' tab at the bottom of the screen to view your book library\n</operation>\n<action>\nclick(x=0.3674, y=0.9192)\n</action>"}], "width": 1440, "height": 3120}
...
```

# Training
Using 8 GPUs to finetnun VLM:
```bash
GPUS=8 bash shell/internvl3_8b_dynamic_res_stage1.sh \
./data/train_meta.json \ # Training data
work_dirs/InternVL3-8B-CUA-exp1 \ # output dir
pretrained/InternVL3-8B-MPO # Based on this pretrained model to finetune the model
```
