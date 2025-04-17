from transformers import AutoTokenizer, AutoModelForCausalLM, TrainingArguments, Trainer
from peft import LoraConfig, get_peft_model, TaskType, prepare_model_for_kbit_training
from datasets import load_dataset
import torch
import os

# Set environment variable for PyTorch MPS memory efficiency
os.environ["PYTORCH_MPS_HIGH_WATERMARK_RATIO"] = "0.0"  # Disable the upper memory limit

# Load tokenizer
model_id = "microsoft/phi-1_5"
tokenizer = AutoTokenizer.from_pretrained(model_id)
tokenizer.pad_token = tokenizer.eos_token

# Load model with CPU fallback since quantization with MPS is problematic
model = AutoModelForCausalLM.from_pretrained(
    model_id,
    device_map="cpu",  # Use CPU to avoid MPS mixed precision issues
    low_cpu_mem_usage=True  # Minimize CPU memory usage
)

# Prepare model for efficient training
model = prepare_model_for_kbit_training(model)

# Configure LoRA with minimal parameters
peft_config = LoraConfig(
    task_type=TaskType.CAUSAL_LM,
    inference_mode=False,
    r=2,  # Very small rank
    lora_alpha=8,
    lora_dropout=0.0,  # No dropout to save compute
    target_modules=["fc2", "out_proj"]  # Target minimal modules
)

# Apply LoRA
model = get_peft_model(model, peft_config)

# Load dataset
dataset = load_dataset('json', data_files='tiny_train.jsonl')

# Create efficient tokenization function
def tokenize_function(examples):
    texts = [f"### Instruction:\n{examples['instruction']}\n\n### Response:\n{examples['output']}"]
    encoded = tokenizer(texts, padding="max_length", truncation=True, max_length=128)  # Small sequence length
    encoded["labels"] = encoded["input_ids"].copy()
    return encoded

# Process dataset
tokenized_dataset = dataset.map(
    tokenize_function, 
    batched=True,
    batch_size=1,
    remove_columns=dataset["train"].column_names
)

# Configure training - without fp16 which caused the error
training_args = TrainingArguments(
    output_dir="phi-lora-minimal",
    per_device_train_batch_size=1,
    gradient_accumulation_steps=1,
    num_train_epochs=3,
    logging_steps=1,
    save_strategy="no",  # Don't save checkpoints
    fp16=False,  # Turn OFF fp16 as it's not supported on MPS
    optim="adamw_torch",
    learning_rate=1e-4,
    weight_decay=0.01,
    max_grad_norm=0.3,  # Gradient clipping
)

# Create trainer
trainer = Trainer(
    model=model,
    args=training_args,
    train_dataset=tokenized_dataset["train"],
)

# Train
trainer.train()

# Save only the LoRA adapter weights
model.save_pretrained("phi-lora-adapter-only")
tokenizer.save_pretrained("phi-lora-adapter-only")