# from django.shortcuts import render , redirect
# from django.http import HttpResponse,JsonResponse
# import numpy as np
# from myapp.models import MyArray
# import re
# import os  
# import sys
# from sklearn.preprocessing import StandardScaler 
# import pandas as pd    
# from keras.models import Sequential
# from keras.layers import LSTM, Dense,Dropout,Bidirectional
# from random import randint
# from sklearn.metrics import mean_squared_error, mean_absolute_error
# import tensorflow as tf
# import random
# from django.views.decorators.csrf import csrf_exempt
# from keras.models import model_from_json
# from django.db.models import Q
# from django.contrib import messages
# import ast
# from sklearn.model_selection import train_test_split
# from keras.layers import Flatten
# from collections import Counter
# import pickle


# model_json_path = "saved_model/AIGuessModel.json"
# model_weights_path = "saved_model/model.weights.h5"
# scaler_path = "saved_model/scaler.pkl"


# count_sequence =1   
# '''
# path = os.path.abspath("database/Data_based_Sequences.txt")
# with open(path, 'r') as file:
#     content = file.read()
# arrays = []
# lines = content.split('\n')
# for line in lines:  
#     # Join the string values with a space to form a single string
#     arr = ' '.join(line.split())
#     # Find all integer values in the string using regex and convert them to integers
#     integer_array = [int(x) for x in re.findall(r'\d+', arr)]
#     arrays.append(integer_array)
# del arrays[-1]


# def SaveDAtabase(request):
#     for arr in arrays: 
#         MyArray.objects.create(data=arr)   
#     return HttpResponse(request,'Random arrays saved!')
# '''
# def home(request):
#     return render(request, "index.html")

# # csrf disabled
# @csrf_exempt
# def add_new_sequence(request):
#     global count_sequence     # Uses global variable
#     try:  
#         if request.method=='POST':
#             # gets input from form
#             NewAddedArray= request.POST.get('array')
#             print("\n NEW ADDED ARRAY :\n",NewAddedArray)
#             # extract all numbers from string
#             integer_array = [int(x) for x in re.findall(r'\d+', NewAddedArray)]  
#             print("\n INTEGER ARRAY :\n",integer_array)
#             # Keeps only numbers ≤ 25
#             filtered_lst = [item for item in integer_array if item <= 25]
#             print("\n FILTERED LIST :\n",filtered_lst)
#             # Removes duplicates
#             New=[i for i in filtered_lst if filtered_lst.count(i)==1]
#             print("\n NEW SEQUENCE :\n",New)
            
#             if len(New) != 10:
#                 print("Sequence length should be 10 digits")
#                 return redirect("/")

#             # Ensures exactly 10 numbers
#             if len(New)==10:
#                 # Gets last ID
#                 # latest_id = MyArray.objects.latest('id').id if MyArray.objects.exists() else 0
#                 latest = MyArray.objects.order_by('-id').first()
#                 latest_id = latest.id if latest else 0
#                 print("\n LATEST ID :\n",latest_id)
#                 # Saves new sequence
#                 # arr_obj = MyArray(id=latest_id+1, data=New,status=1)
#                 MyArray.objects.create(data=New, status=1)
                
#                 # arr_obj = MyArray(id=latest_id+1, data=New)   
#                 # arr_obj.save()
#                 # Counts new sequences
#                 num_status_1 = MyArray.objects.filter(status=1).count()
#                 print("\nNUM STATUS 1\n:",num_status_1)

#                 # If condition met → train model
#                 # if num_status_1 == count_sequence:
#                 model_exists = os.path.exists(model_json_path) and os.path.exists(model_weights_path)
#                 # Marks data as used

#                 # Fetch data
#                 data = MyArray.objects.all().values()
#                 print("\nDATA:\n",data)
#                 # prepare_data(request ,data)

#                 # extracts only "data" field
#                 arrays=[]
#                 for list_values in data:
#                     for key, value in list_values.items():
#                         if key == 'data':
#                             arrays.append(value)

#                 # converts string to list
#                 # sequence=[ast.literal_eval(arr) for arr in arrays]
#                 sequence = []
#                 for arr in arrays:
#                     if isinstance(arr, str):
#                         sequence.append(ast.literal_eval(arr))
#                     else:
#                         sequence.append(arr)
#                 print("\nSEQUENCE:\n",sequence)
#                 # creates dataframe
#                 df=pd.DataFrame(sequence,columns =[f'seq_{i}' for i in range(1,11)])
#                 print("\nDF:\n",df)

#                 if os.path.exists(scaler_path):
#                     print("\n Loading existing scaler...")
#                     with open(scaler_path, "rb") as f:
#                         scaler = pickle.load(f)
#                 else:
#                     print("\n Creating new scaler...")
#                     scaler = StandardScaler().fit(df.values)
#                     with open(scaler_path, "wb") as f:
#                         pickle.dump(scaler, f)

#                 transformed_dataset = scaler.transform(df.values)
#                 transformed_df = pd.DataFrame(data=transformed_dataset, index=df.index)
#                 # data scaling
#                 # scaler=StandardScaler().fit(df.values)

#                 # Define gyper params of model
#                 number_of_rows=df.shape[0]
#                 print("\nNUMBER OF ROWS:\n",number_of_rows)

#                 # model parameters and Use 4 past sequences to predict next
#                 window_length , n_feature = 4, 10     # time steps     # steps to predict
#                 if number_of_rows <= window_length:
#                     print(" Not enough data to train model")
#                     return redirect("/")
#                 # create training data
#                 input=np.zeros([number_of_rows-window_length ,window_length,10], dtype=float)
#                 print("\nINPUT:\n",input)
#                 output=np.zeros([number_of_rows-window_length,n_feature],dtype=float)
#                 print("\nOUTPUT:\n",output)
#                 # Creates sliding window
#                 for i in range(0,number_of_rows - window_length):
#                     input_window = transformed_df.iloc[i:i+window_length, :10].values
#                     input[i] = input_window
#                     output_window = transformed_df.iloc[i+window_length:i+window_length+1, :n_feature].values
#                     output[i] = output_window.squeeze()

#                 train_x,test_x,train_y,test_y = train_test_split(input,output,test_size=0.25,random_state=42)

#                 if not model_exists:
#                     print("Training new model")
#                     # model building
#                     model = Sequential()
#                     # Multiple layers:
#                     model.add(Bidirectional(LSTM(240,return_sequences=True,input_shape=(window_length,n_feature))))
#                     model.add(Dropout(0.2))
#                     model.add(Bidirectional(LSTM(240,return_sequences=True, input_shape=(window_length,n_feature))))
#                     model.add(Dropout(0.2))
#                     model.add(Bidirectional(LSTM(240,return_sequences=True, input_shape=(window_length,n_feature))))
#                     model.add(Dropout(0.2))
#                     model.add(Bidirectional(LSTM(240,return_sequences=True, input_shape=(window_length,n_feature))))
#                     model.add(Dropout(0.2))
#                     model.add(Bidirectional(LSTM(240,return_sequences=True, input_shape=(window_length,n_feature))))
#                     model.add(Dropout(0.2)  )
#                     model.add(Bidirectional(LSTM(240,return_sequences=False, input_shape=(window_length,n_feature))))
#                     # Output layer (10 values)
#                     model.add(Dense(n_feature))
                
#                     # # compile
#                     model.compile(optimizer='adam',loss = 'mse',metrics=['accuracy'])
#                     # # train
#                     # model.fit(train_x, train_y, epochs=500, batch_size=100, verbose=1,shuffle=False)
#                     model.fit(train_x, train_y, epochs=10, batch_size=32, verbose=1)
#                     # save model
#                     model_json = model.to_json()
#                     with open("saved_model/AIGuessModel.json", "w") as json_file:
#                         json_file.write(model_json)   

#                     model.save_weights("saved_model/model.weights.h5")
#                     print("MOEDL TRAINED AND SAVED SUCCESSFULLY,")
#                 else:
#                     print("\n Loading existing model...")
#                     with open(model_json_path,"r") as file:
#                         loaded_model_json = file.read()

#                     model = model_from_json(loaded_model_json)
#                     model.load_weights(model_weights_path)

#                     model.compile(optimizer='adam', loss="mse", metrics=["accuracy"])

#                 # prediction
#                 last_sequence=transformed_df.iloc[-window_length:,:]
#                 print("\nLAST SEQUENCE:\n",last_sequence)
#                 # scaled_input = scaler.transform(last_sequence.values)
#                 scaled_input = last_sequence.values
#                 if scaled_input.shape != (window_length, n_feature):
#                     print("Invalid input shape")
#                     return redirect("/")
#                 print("\nSCALED INPUT:\n",scaled_input)
#                 predicted_output = model.predict(scaled_input.reshape(1,window_length,n_feature),batch_size=100,verbose=1)
#                 print("\nPREDICTED OUTPUT:\n",predicted_output)
#                 # Convert back to original scale
#                 output=scaler.inverse_transform(predicted_output).astype(int)
#                 print("\nOUTPUT:\n",output)
#                 # Takes recent sequences
#                 input_sequence1= df.iloc[-1:].values
#                 input_sequence2= df.iloc[-2:].values
#                 input_sequence3= df.iloc[-3:].values
#                 input_sequence4= df.iloc[-4:].values 
#                 input_sequence5= df.iloc[-5:].values 

#                 # scl_input=scaler.inverse_transform(input_sequence).astype(int)
#                 MyArray.objects.filter(status=1).update(status=2)

#                 # Flatten list
#                 input1=[integer for x in input_sequence1 for integer in x]
#                 input2=[integer for x in input_sequence2 for integer in x]
#                 input3=[integer for x in input_sequence3 for integer in x]
#                 input4=[integer for x in input_sequence4 for integer in x]
#                 input5=[integer for x in input_sequence5 for integer in x]
                
#                 # combine input + output
#                 all_words1=np.concatenate([input1,output.flatten()])
#                 all_words2=np.concatenate([input2,output.flatten()])
#                 all_words3=np.concatenate([input3,output.flatten()])
#                 all_words4=np.concatenate([input4,output.flatten()])
#                 all_words5=np.concatenate([input5,output.flatten()])

#                 # FREQUENCY COUNT
#                 freq1=Counter(all_words1)
#                 freq2=Counter(all_words2)
#                 freq3=Counter(all_words3)
#                 freq4=Counter(all_words4)
#                 freq5=Counter(all_words5)

#                 # Top 3 frequent numbers
#                 most_repeated_prob1=[x[0] for x in freq1.most_common(3)]
#                 most_repeated_prob2=[x[0] for x in freq2.most_common(3)]
#                 most_repeated_prob3=[x[0] for x in freq3.most_common(3)]
#                 most_repeated_prob4=[x[0] for x in freq4.most_common(3)]
#                 most_repeated_prob5=[x[0] for x in freq5.most_common(3)]

#                 # Final result
#                 random_value=[most_repeated_prob1,
#                         most_repeated_prob2,
#                         most_repeated_prob3,
#                         most_repeated_prob4,
#                         most_repeated_prob5]
#                 print("\nRANDOM VALUE:\n",random_value)
#                 return render(request , "genrate.html" ,{"random_values":random_value})

#             else:
#                 print("Sequence length should be 10 digits")
#                 return redirect("/")
#         else:
#             return redirect("/")
#     except Exception as e:
#         exc_type , exc_obj , exc_tb = sys.exc_info()
#         print(f" error occur |: {str(e)} in line no : {exc_tb.tb_lineno}")
#         return HttpResponse("Something went wrong")
              
# def array_history(request):
#     recent_sequences = MyArray.objects.filter(Q(status=1) | Q(status=2))
#     print(recent_sequences)
#     return render(request, 'history.html' , {'recent_sequences':recent_sequences})  

# @csrf_exempt
# def Reset_history(request):
#     recent_sequences = MyArray.objects.filter(Q(status=1) | Q(status=2))
#     val = request.POST.get('input')
#     if request.method=='POST':
#         val = request.POST.getlist('input')
#         if val:
#             val=list(map(int,val))
#             for i in val:
#                 MyArray.objects.filter(id=i).delete()
#                 messages.success(request, "Selected sequences have been deleted.")
#             return  redirect('/')
#         else:
#             messages.warning(request, "No sequences were selected.")
        
#     return render(request, 'reset.html' , {'recent_sequences':recent_sequences})



















from django.shortcuts import render , redirect
from django.http import HttpResponse,JsonResponse
import numpy as np
from myapp.models import MyArray
import re
import os  
import sys
from sklearn.preprocessing import StandardScaler 
import pandas as pd    
from keras.models import Sequential
from keras.layers import LSTM, Dense,Dropout,Bidirectional
from random import randint
from sklearn.metrics import mean_squared_error, mean_absolute_error
import tensorflow as tf
import random
from django.views.decorators.csrf import csrf_exempt
from keras.models import model_from_json
from django.db.models import Q
from django.contrib import messages
import ast
from sklearn.model_selection import train_test_split
from keras.layers import Flatten
from collections import Counter
import pickle


model_json_path = "saved_model/AIGuessModel.json"
model_weights_path = "saved_model/model.weights.h5"
scaler_path = "saved_model/scaler.pkl"


count_sequence = 1   

'''
path = os.path.abspath("database/Data_based_Sequences.txt")
with open(path, 'r') as file:
    content = file.read()
arrays = []
lines = content.split('\n')
for line in lines:  
    arr = ' '.join(line.split())
    integer_array = [int(x) for x in re.findall(r'\d+', arr)]
    arrays.append(integer_array)
del arrays[-1]


def SaveDAtabase(request):
    for arr in arrays: 
        MyArray.objects.create(data=arr)   
    return HttpResponse(request,'Random arrays saved!')
'''

def home(request):
    return render(request, "index.html")


@csrf_exempt
def add_new_sequence(request):
    global count_sequence
    try:  
        if request.method == 'POST':
            NewAddedArray = request.POST.get('array')
            print("\n NEW ADDED ARRAY :\n", NewAddedArray)

            integer_array = [int(x) for x in re.findall(r'\d+', NewAddedArray)]  
            print("\n INTEGER ARRAY :\n", integer_array)

            filtered_lst = [item for item in integer_array if item <= 25]
            print("\n FILTERED LIST :\n", filtered_lst)

            New = [i for i in filtered_lst if filtered_lst.count(i) == 1]
            print("\n NEW SEQUENCE :\n", New)
            
            if len(New) != 10:
                print("Sequence length should be 10 digits")
                return redirect("/")

            if len(New) == 10:
                latest = MyArray.objects.order_by('-id').first()
                latest_id = latest.id if latest else 0
                print("\n LATEST ID :\n", latest_id)

                MyArray.objects.create(data=New, status=1)

                num_status_1 = MyArray.objects.filter(status=1).count()
                print("\nNUM STATUS 1\n:", num_status_1)

                model_exists = os.path.exists(model_json_path) and os.path.exists(model_weights_path)

                data = MyArray.objects.all().values()
                print("\nDATA:\n", data)

                arrays = []
                for list_values in data:
                    for key, value in list_values.items():
                        if key == 'data':
                            arrays.append(value)

                sequence = []
                for arr in arrays:
                    if isinstance(arr, str):
                        sequence.append(ast.literal_eval(arr))
                    else:
                        sequence.append(arr)

                print("\nSEQUENCE:\n", sequence)

                df = pd.DataFrame(sequence, columns=[f'seq_{i}' for i in range(1, 11)])
                print("\nDF:\n", df)

                if os.path.exists(scaler_path):
                    print("\n Loading existing scaler...")
                    with open(scaler_path, "rb") as f:
                        scaler = pickle.load(f)
                else:
                    print("\n Creating new scaler...")
                    scaler = StandardScaler().fit(df.values)
                    with open(scaler_path, "wb") as f:
                        pickle.dump(scaler, f)

                transformed_dataset = scaler.transform(df.values)
                transformed_df = pd.DataFrame(data=transformed_dataset, index=df.index)

                number_of_rows = df.shape[0]
                print("\nNUMBER OF ROWS:\n", number_of_rows)

                window_length, n_feature = 4, 10
                if number_of_rows <= window_length:
                    print(" Not enough data to train model")
                    return redirect("/")

                input = np.zeros([number_of_rows - window_length, window_length, 10], dtype=float)
                print("\nINPUT:\n", input)

                output = np.zeros([number_of_rows - window_length, n_feature], dtype=float)
                print("\nOUTPUT:\n", output)

                for i in range(0, number_of_rows - window_length):
                    input_window = transformed_df.iloc[i:i + window_length, :10].values
                    input[i] = input_window

                    output_window = transformed_df.iloc[i + window_length:i + window_length + 1, :n_feature].values
                    output[i] = output_window.squeeze()

                train_x, test_x, train_y, test_y = train_test_split(input, output, test_size=0.25, random_state=42)

                if not model_exists:
                    print("Training new model")

                    model = Sequential()
                    model.add(Bidirectional(LSTM(240, return_sequences=True, input_shape=(window_length, n_feature))))
                    model.add(Dropout(0.2))
                    model.add(Bidirectional(LSTM(240, return_sequences=True, input_shape=(window_length, n_feature))))
                    model.add(Dropout(0.2))
                    model.add(Bidirectional(LSTM(240, return_sequences=True, input_shape=(window_length, n_feature))))
                    model.add(Dropout(0.2))
                    model.add(Bidirectional(LSTM(240, return_sequences=True, input_shape=(window_length, n_feature))))
                    model.add(Dropout(0.2))
                    model.add(Bidirectional(LSTM(240, return_sequences=True, input_shape=(window_length, n_feature))))
                    model.add(Dropout(0.2))
                    model.add(Bidirectional(LSTM(240, return_sequences=False, input_shape=(window_length, n_feature))))
                    model.add(Dense(n_feature))

                    model.compile(optimizer='adam', loss='mse', metrics=['accuracy'])
                    model.fit(train_x, train_y, epochs=10, batch_size=32, verbose=1)

                    model_json = model.to_json()
                    with open("saved_model/AIGuessModel.json", "w") as json_file:
                        json_file.write(model_json)

                    model.save_weights("saved_model/model.weights.h5")
                    print("MOEDL TRAINED AND SAVED SUCCESSFULLY,")

                else:
                    print("\n Loading existing model...")
                    with open(model_json_path, "r") as file:
                        loaded_model_json = file.read()

                    model = model_from_json(loaded_model_json)
                    model.load_weights(model_weights_path)
                    model.compile(optimizer='adam', loss="mse", metrics=["accuracy"])

                last_sequence = transformed_df.iloc[-window_length:, :]
                print("\nLAST SEQUENCE:\n", last_sequence)

                scaled_input = last_sequence.values
                if scaled_input.shape != (window_length, n_feature):
                    print("Invalid input shape")
                    return redirect("/")

                print("\nSCALED INPUT:\n", scaled_input)

                predicted_output = model.predict(
                    scaled_input.reshape(1, window_length, n_feature),
                    batch_size=100,
                    verbose=1
                )

                print("\nPREDICTED OUTPUT:\n", predicted_output)

                output = scaler.inverse_transform(predicted_output).astype(int)
                print("\nOUTPUT:\n", output)

                input_sequence1 = df.iloc[-1:].values
                input_sequence2 = df.iloc[-2:].values
                input_sequence3 = df.iloc[-3:].values
                input_sequence4 = df.iloc[-4:].values 
                input_sequence5 = df.iloc[-5:].values 

                MyArray.objects.filter(status=1).update(status=2)

                input1 = [integer for x in input_sequence1 for integer in x]
                input2 = [integer for x in input_sequence2 for integer in x]
                input3 = [integer for x in input_sequence3 for integer in x]
                input4 = [integer for x in input_sequence4 for integer in x]
                input5 = [integer for x in input_sequence5 for integer in x]
                
                all_words1 = np.concatenate([input1, output.flatten()])
                all_words2 = np.concatenate([input2, output.flatten()])
                all_words3 = np.concatenate([input3, output.flatten()])
                all_words4 = np.concatenate([input4, output.flatten()])
                all_words5 = np.concatenate([input5, output.flatten()])

                freq1 = Counter(all_words1)
                freq2 = Counter(all_words2)
                freq3 = Counter(all_words3)
                freq4 = Counter(all_words4)
                freq5 = Counter(all_words5)

                most_repeated_prob1 = [x[0] for x in freq1.most_common(3)]
                most_repeated_prob2 = [x[0] for x in freq2.most_common(3)]
                most_repeated_prob3 = [x[0] for x in freq3.most_common(3)]
                most_repeated_prob4 = [x[0] for x in freq4.most_common(3)]
                most_repeated_prob5 = [x[0] for x in freq5.most_common(3)]

                random_value = [
                    most_repeated_prob1,
                    most_repeated_prob2,
                    most_repeated_prob3,
                    most_repeated_prob4,
                    most_repeated_prob5
                ]

                print("\nRANDOM VALUE:\n", random_value)

                return render(request, "genrate.html", {"random_values": random_value})

            else:
                print("Sequence length should be 10 digits")
                return redirect("/")

        else:
            return redirect("/")

    except Exception as e:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        print(f" error occur |: {str(e)} in line no : {exc_tb.tb_lineno}")
        return HttpResponse("Something went wrong")
              

def array_history(request):
    recent_sequences = MyArray.objects.filter(Q(status=1) | Q(status=2))
    print(recent_sequences)
    return render(request, 'history.html', {'recent_sequences': recent_sequences})  


@csrf_exempt
def Reset_history(request):
    recent_sequences = MyArray.objects.filter(Q(status=1) | Q(status=2))
    val = request.POST.get('input')

    if request.method == 'POST':
        val = request.POST.getlist('input')
        if val:
            val = list(map(int, val))
            for i in val:
                MyArray.objects.filter(id=i).delete()
                messages.success(request, "Selected sequences have been deleted.")
            return redirect('/')
        else:
            messages.warning(request, "No sequences were selected.")
        
    return render(request, 'reset.html', {'recent_sequences': recent_sequences})