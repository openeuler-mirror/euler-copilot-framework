from transformers import AutoModelForCausalLM, AutoTokenizer
import torch
from transformers import BertTokenizer, BertModel
# import bitsandbytes as bnb
# import os
# os.environ["CUDA_VISIBLE_DEVICES"] = "2,3"

# 加载模型和tokenizer
def getModel(model_path = "/home/nfs02/model/Qwen1.5-14B-Chat"):
    tokenizer = AutoTokenizer.from_pretrained(model_path)
    # 加载模型,8bit
    model = AutoModelForCausalLM.from_pretrained(model_path, load_in_8bit=True)
    if torch.cuda.device_count() >= 1:
        print(f"使用 {torch.cuda.device_count()} 块 GPU!")
        model = torch.nn.DataParallel(model)
    # 如果有GPU可用，使用GPU，否则使用CPU cuda
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device)
    return model, tokenizer, device

bertFlag = False
if bertFlag:
    bertTokenizer = BertTokenizer.from_pretrained('bert-base-uncased')
    bertModel = BertModel.from_pretrained('bert-base-uncased')