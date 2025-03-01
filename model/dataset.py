from datasets import load_dataset
from transformers import AutoTokenizer
import torch

class SFTDataset:
    def __init__(self,tokenizer_path, max_seq_len, data_path = 'CohleM/lillm-sft-dataset-v1'):
        self.data = load_dataset(data_path)
        self.max_seq_len = max_seq_len
        self.tokenizer = AutoTokenizer.from_pretrained(tokenizer_path)
        self.filtered_data = self.data.filter(self._filter_by_token_len, num_proc = 8)
        self.tokenized_data = self.filtered_data.map(self._tokenize, num_proc = 8)

    def _filter_by_token_len(self, example):
        template = self._add_chat_format(example)
        return len(self.tokenizer.encode(template)) < self.max_seq_len
    
    def _add_chat_format(self, example):
        items = example['conversation']
        template = ""
        
        for item in items:

            if item['role'] == 'user':
                template += f"<r0>{item['role']}<r1>" + f"{item['content']}</r2>"
            elif item['role'] =='assistant':
                template += f"<r0>{item['role']}<r1>" + f"{item['content']}</s>"
        return template

    def _generate_loss_mask(self, tokenized_input):
        assistant_token = self.tokenizer.encode('<r0>assistant<r1>')
        end_token = self.tokenizer.encode('</s>')[0]

        assist_token_idx = [i+3 for i in range(len(tokenized_input)) if tokenized_input[i:i+3] == assistant_token]
        end_token_idx = [i for i,v in enumerate(tokenized_input) if v == end_token]

        loss_mask = [0]*len(tokenized_input)

        for i in range(len(assist_token_idx)):
            loss_mask[assist_token_idx[i]: end_token_idx[i] + 1] = [1]* (end_token_idx[i] - assist_token_idx[i] + 1)

        return loss_mask

        
    def _tokenize(self,example):
        template = self._add_chat_format(example)

        x = self.tokenizer.encode(template)

        x += (self.max_seq_len - len(x))* [0]
        x = x[:self.max_seq_len]
        
        X = torch.tensor(x[:-1], dtype=torch.long)
        Y = torch.tensor(x[1:], dtype=torch.long)
        
        loss_mask = self._generate_loss_mask(x[1:])
        
        loss_mask = torch.tensor(loss_mask, dtype=torch.long)
        
        return {'X': X, 'Y': Y, 'loss_mask': loss_mask}
    
    
    def get_batch(self, split, batch_size):
        batches = torch.randint(0, self.tokenized_data[split].num_rows, (batch_size,))
        out = self.tokenized_data[split][batches]
        
        return torch.tensor(out['X'], dtype=torch.long), torch.tensor(out['Y'], dtype=torch.long) , torch.tensor(out['loss_mask'], dtype=torch.long)

    
