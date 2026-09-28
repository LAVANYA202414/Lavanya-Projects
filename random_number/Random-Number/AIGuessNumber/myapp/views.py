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
from django.contrib import messages
from tensorflow.keras.utils import plot_model
from tensorflow.keras.callbacks import TensorBoard

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
            # -> Get user input
            NewAddedArray = request.POST.get('array')
            # print("\n NEW ADDED ARRAY :\n", NewAddedArray)

            # -> Extract numbers only
            integer_array = [int(x) for x in re.findall(r'\d+', NewAddedArray)]  
            # print("\n INTEGER ARRAY :\n", integer_array)

            # -> Only less than or equal to 25 allowed
            filtered_lst = [item for item in integer_array if item <= 25]
            # print("\n FILTERED LIST :\n", filtered_lst)

            # -> Remove duplicates
            # New = [i for i in filtered_lst if filtered_lst.count(i) == 1]
            # if New:
            #     messages.error(request, "Duplicates are not allowed in the sequence!")
            #     return redirect("/")
            # print("\n NEW SEQUENCE :\n", New)
            if len(filtered_lst) != len(set(filtered_lst)):
                messages.error(request, "Duplicates are not allowed in the sequence!")
                return redirect("/")

            # -> Use the filtered list directly (no need to filter again)
            New = filtered_lst
            
            # -> Must have exactly 10 numbers
            if len(New) != 10:
                messages.error(request, "Sequence length should be 10 digits!")
                return redirect("/")

            if len(New) == 10:
                latest = MyArray.objects.order_by('-id').first()
                latest_id = latest.id if latest else 0
                # print("\n LATEST ID :\n", latest_id)

                # -> Save in database
                MyArray.objects.create(data=New, status=1)

                num_status_1 = MyArray.objects.filter(status=1).count()
                # print("\nNUM STATUS 1\n:", num_status_1)

                model_exists = os.path.exists(model_json_path) and os.path.exists(model_weights_path)

                # -> Load all data
                data = MyArray.objects.all().values()
                # print("\nDATA:\n", data)

                arrays = []
                for list_values in data:
                    for key, value in list_values.items():
                        if key == 'data':
                            # -> Extract sequences
                            arrays.append(value)

                sequence = []
                for arr in arrays:
                    if isinstance(arr, str):
                        # -> Convert str to list
                        sequence.append(ast.literal_eval(arr))
                    else:
                        sequence.append(arr)

                # print("\nSEQUENCE:\n", sequence)

                # -> Convert to dataframe
                df = pd.DataFrame(sequence, columns=[f'seq_{i}' for i in range(1, 11)])
                # print("\nDF:\n", df)

                if os.path.exists(scaler_path):
                    # Scaler is a tool that changes your data into standard format so the model can learn better
                    # -> Scaler is a tool that normalizes data so the model can learn properly
                    print("\n Loading existing scaler...")
                    with open(scaler_path, "rb") as f:
                        scaler = pickle.load(f)
                else:
                    print("\n Creating new scaler...")
                    # -> Scaling --> normalize data
                    scaler = StandardScaler().fit(df.values)
                    with open(scaler_path, "wb") as f:
                        # -> Saved
                        pickle.dump(scaler, f)

                # -> Transform data --> take original data amd convert it into scaled values using the scalar
                transformed_dataset = scaler.transform(df.values)
                transformed_df = pd.DataFrame(data=transformed_dataset, index=df.index)

                number_of_rows = df.shape[0]
                # print("\nNUMBER OF ROWS:\n", number_of_rows)

                # -> creating training data --> model looks at last 4 sequences to predict next
                    # -> window lenght = how many past sequences to look at
                    # -> n_feature = how many numbers in each sequence
                window_length, n_feature = 4, 10
                if number_of_rows <= window_length:
                    print(" Not enough data to train model")
                    return redirect("/")

                input = np.zeros([number_of_rows - window_length, window_length, 10], dtype=float)
                # print("\nINPUT:\n", input)

                output = np.zeros([number_of_rows - window_length, n_feature], dtype=float)
                # print("\nOUTPUT:\n", output)

                for i in range(0, number_of_rows - window_length):
                    input_window = transformed_df.iloc[i:i + window_length, :10].values
                    input[i] = input_window

                    output_window = transformed_df.iloc[i + window_length:i + window_length + 1, :n_feature].values
                    output[i] = output_window.squeeze()

                train_x, test_x, train_y, test_y = train_test_split(input, output, test_size=0.25, random_state=42)

                tensorboard = TensorBoard(log_dir="logs")

                if not model_exists:
                    print("Training new model")

                    # -> Model creation
                    model = Sequential()
                    # -> Multiple LSTM layers --> To capture deep patterns in sequences
                        # -> 240 = number of neurons in this layer
                        # -> return_sequences = True --> return output for each time step
                    model.add(Bidirectional(LSTM(240, return_sequences=True, input_shape=(window_length, n_feature))))
                    # -> Drop is a technique to prevent overfitting
                        # -> 0.2 = 20%. 20% neurons are ignored and 80% neurons are active
                        # -> To reduce overfitting
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
                    # -> A NN layer where every neuron receives input from all neurons in the previous layer
                    model.add(Dense(n_feature))

                    # -> Compile model
                        # -> optimizer --> controls how weights are adjusted
                        # -> loss --> how wrong is the model
                        # -> metric --> it shows performance during training
                    model.compile(optimizer='adam', loss='mse', metrics=['accuracy'])
                    # -> Train model
                        # -> train_x = past sequences(input data) , train_y = next sequences(output data)
                        # -> epochs --> one full pass over the entire training data
                        # -> batch_size --> instead of training on all the data at once, data is split into small groups
                        # -> verbose --> controls output display
                        # -> call_backs --> a function that runs during  training
                    model.fit(train_x, train_y, epochs=500, batch_size=32, verbose=1 ,callbacks=[tensorboard])
                    # -> Save model
                    model_json = model.to_json()
                    with open("saved_model/AIGuessModel.json", "w") as json_file:
                        json_file.write(model_json)

                    model.save_weights("saved_model/model.weights.h5")
                    print("MOEDL TRAINED AND SAVED SUCCESSFULLY,")

                else:
                    print("\n Loading existing model...")
                    # -> Load model if exists
                    with open(model_json_path, "r") as file:
                        loaded_model_json = file.read()

                    model = model_from_json(loaded_model_json)
                    model.load_weights(model_weights_path)
                    model.compile(optimizer='adam', loss="mse", metrics=["accuracy"])

                # -> Plot model --> Saves diagram image
                plot_model(
                    model,
                    to_file='model_structure.png',
                    show_shapes=True,
                    show_layer_names=True
                )

                last_sequence = transformed_df.iloc[-window_length:, :]
                # print("\nLAST SEQUENCE:\n", last_sequence)

                scaled_input = last_sequence.values
                if scaled_input.shape != (window_length, n_feature):
                    print("Invalid input shape")
                    return redirect("/")

                print("\nSCALED INPUT:\n", scaled_input)
                
                # -> Prediction
                predicted_output = model.predict(
                    scaled_input.reshape(1, window_length, n_feature),
                    batch_size=100,
                    verbose=1
                )

                # print("\nPREDICTED OUTPUT:\n", predicted_output)

                # -> Convert back to original scale
                output = scaler.inverse_transform(predicted_output).astype(int)
                # print("\nOUTPUT:\n", output)

                # -> Take last five sequences
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
                
                # -> Combine with predicted outputs
                all_words1 = np.concatenate([input1, output.flatten()])
                all_words2 = np.concatenate([input2, output.flatten()])
                all_words3 = np.concatenate([input3, output.flatten()])
                all_words4 = np.concatenate([input4, output.flatten()])
                all_words5 = np.concatenate([input5, output.flatten()])

                # -> Count frequency
                freq1 = Counter(all_words1)
                freq2 = Counter(all_words2)
                freq3 = Counter(all_words3)
                freq4 = Counter(all_words4)
                freq5 = Counter(all_words5)

                # -> Get top 3 numbers
                most_repeated_prob1 = [x[0] for x in freq1.most_common(3)]
                most_repeated_prob2 = [x[0] for x in freq2.most_common(3)]
                most_repeated_prob3 = [x[0] for x in freq3.most_common(3)]
                most_repeated_prob4 = [x[0] for x in freq4.most_common(3)]
                most_repeated_prob5 = [x[0] for x in freq5.most_common(3)]

                # -> Final output --> returns 5 set of predictions
                random_value = [
                    most_repeated_prob1,
                    most_repeated_prob2,
                    most_repeated_prob3,
                    most_repeated_prob4,
                    most_repeated_prob5
                ]

                # print("\nRANDOM VALUE:\n", random_value)
                
                # -> Render result
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