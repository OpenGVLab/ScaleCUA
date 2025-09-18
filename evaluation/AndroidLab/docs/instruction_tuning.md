# Android Instruct Guide

## Data Download

Please download the Android Instruct dataset from [this link](https://drive.google.com/file/d/1s0b74VEOww9n1kMocd6RJivwaUCymEs4/view?usp=drive_link). The dataset has been organized in the llama factory training data format. It includes 6,208 steps in XML format and 6,053 steps in SoM format. A small number of steps are missing due to certain special pages that could not be converted into the SoM format and were therefore removed. Our training is also based on this version of the dataset.

## Training Details

For **Llama3.1-8B**, **GLM4-9B**, **Qwen2-7B**, and **Qwen2-VL-7B**, we used the **Llama factory** framework for training. For **CogVLM** and **Llama3.2-11B-Vision**, we utilized the **Swift** framework for training. All training was conducted with a learning rate of **1e-5** and over **3 epochs**. Testing was performed using **vllm** deployment with greedy decoding.