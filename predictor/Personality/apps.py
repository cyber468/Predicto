from django.apps import AppConfig
import pandas as pd
import pickle


class PersonalityConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'Personality'    
    model=pickle.load(open(r"F:\Django\\ml\\models\\final_model.pkl","rb"))
    dataset=pd.read_csv(r"F:\\Django\\ml\\data\\data-final.csv",delimiter='\t')
