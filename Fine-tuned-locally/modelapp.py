from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM
from peft import PeftModel, PeftConfig
import warnings

# Configure for Apple Silicon CPU-only
torch.set_default_device('cpu')
torch.set_default_dtype(torch.float32)
warnings.filterwarnings("ignore")

app = FastAPI()

class Request(BaseModel):
    instruction: str
    max_new_tokens: int = 128  # Reduced for CPU performance
    temperature: float = 0.7
    top_p: float = 0.9

def load_model():
    try:
        print("Loading adapter config...")
        config = PeftConfig.from_pretrained("phi-lora-adapter-only")
        
        print("Loading tokenizer...")
        tokenizer = AutoTokenizer.from_pretrained(config.base_model_name_or_path)
        tokenizer.pad_token = tokenizer.eos_token
        
        print("Loading base model (CPU only, this may take a while)...")
        base_model = AutoModelForCausalLM.from_pretrained(
            config.base_model_name_or_path,
            torch_dtype=torch.float32,
            device_map="cpu",
            low_cpu_mem_usage=True,
            trust_remote_code=True
        )
        
        print("Loading adapter...")
        model = PeftModel.from_pretrained(
            base_model,
            "phi-lora-adapter-only",
            device_map="cpu"
        )
        
        print("Merging adapter...")
        model = model.merge_and_unload()
        model.eval()
        
        print("Model loaded successfully on CPU!")
        return model, tokenizer
        
    except Exception as e:
        print(f"Error loading model: {str(e)}")
        raise

# Initialize model
try:
    model, tokenizer = load_model()
except Exception as e:
    print(f"Failed to initialize model: {str(e)}")
    model, tokenizer = None, None

@app.post("/predict")
async def predict(request: Request):
    if not model or not tokenizer:
        raise HTTPException(503, detail="Model not loaded")
    
    try:
        prompt = f"### Instruction:\n{request.instruction}\n\n### Response:\n"
        inputs = tokenizer(prompt, return_tensors="pt").to('cpu')
        
        # Force CPU execution
        with torch.no_grad():
            outputs = model.generate(
                input_ids=inputs.input_ids,
                attention_mask=inputs.attention_mask,
                max_new_tokens=request.max_new_tokens,
                temperature=request.temperature,
                top_p=request.top_p,
                do_sample=True,
                pad_token_id=tokenizer.eos_token_id
            )
        
        response = tokenizer.decode(outputs[0], skip_special_tokens=True)
        return {"response": response.split("### Response:\n")[-1].strip()}
    
    except Exception as e:
        raise HTTPException(500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)