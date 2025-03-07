from transformers import MarianTokenizer, MarianMTModel
import torch
import os
import time
from typing import List
from textblob import TextBlob

QUEUE = []


def time_me(func):
    """
    Decorator to test function execution time.
    Useful in development
    """
    global QUEUE
              
    def inner(*args):
        """ Enable deactivation of timer"""
        global QUEUE

        if not args[0].timer:
            return func(*args)

        # Time
        t1 = time.time()
        out = func(*args)
        t2 = time.time()

        # Print and return
        document = {'project':'translate',
                    'func_name':func.__name__,
                    'class_name':args[0].name,
                    'elapsed_time':round(t2 - t1, 3), 
                    'timestamp': t1,
                    'model':args[0].model_on_cuda}
        
        QUEUE.append(document)
        return out

    return inner


class Translator():
    def __init__(self, models_dir, device):
        # Dashboards
        self.name = 'OPUS'
        self.timer = False

        # Model
        self.models = {}
        self.models_dir = models_dir
        self.model_on_cuda = ''
        self.device = device

    def get_supported_langs(self):
        """
        Parse translation model so that supported lamguages are extracted
        """
        routes = [x.split('-')[-2:] for x in os.listdir(self.models_dir)]
        return routes

    def to_cuda(self, model_route):
        """Logic for switching models"""

        # Same as on CUDA, skip
        if self.model_on_cuda == model_route:
            return 'success'
        
        # If other model is on CUDA, remove
        if self.model_on_cuda in self.models:
            self.models[self.model_on_cuda][0].cpu()
            torch.cuda.empty_cache()
        
        # Move new model to CUDA
        self.models[model_route][0].cuda()
        self.model_on_cuda = model_route

        return f"successfully loaded model for {model_route} transation"

    def load_model(self, route):
        """
        Load model from path --> Auto dowload not yet implemented
        """
        # Make model name from params
        model = f'opus-mt-{route}'
        path = os.path.join(self.models_dir, model)

        try:
            # Load model locally
            model = MarianMTModel.from_pretrained(path)
            tok = MarianTokenizer.from_pretrained(path)

        except:
            # Model not yet downloaded
            return 0, f"make sure you have downloaded model for {route} translation"

        # Save model in RAM
        self.models[route] = (model,tok)
        return 1, f"successfully loaded model for {route} transation"

    def translate(self, source, target, text, batch_size = 32):
        """
        - First select model and check existence
        - Then translate text per sentence, batch sentences by 30.
        """
        route = f'{source}-{target}'
        message = 'success'

        # Load model in route if not yet there
        if not self.models.get(route):
            success_code, message = self.load_model(route)

            if not success_code:
                return "", message

        if self.device == 'cuda':
            message = self.to_cuda(route)

        # Crop into sentences
        blobs = TextBlob(text)
        texts = [sentence.string for sentence in blobs.sentences]
        
        # Start Sentences level batching
        words: List[str] = []
        for sub_index in range(0, len(texts), batch_size):
    
            # Tokenize; max 30 sentences a piece
            batch = self.models[route][1](texts[sub_index:sub_index+batch_size], 
                        return_tensors="pt", 
                        padding=True, 
                        truncation=True)
            
            # To GPU
            if self.models[route][0].device.type != 'cpu':
                batch = {k:v.cuda() for k,v in batch.items()}
            
            # Translate tokens
            with torch.no_grad():
                gen = self.models[route][0].generate(**batch)
            
            # Tokens to words
            words += self.models[route][1].batch_decode(gen.cpu(), skip_special_tokens=True) 


        # Return as one string
        return ''.join(words), message