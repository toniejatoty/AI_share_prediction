from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.preprocessing import MinMaxScaler
import numpy as np
from tensorflow.keras.models import Sequential  # type: ignore
from tensorflow.keras.layers import LSTM, Dense, Dropout  # type: ignore
from tensorflow.keras.optimizers import Adam, SGD, RMSprop # type: ignore

def predict_stock_prices(
    df_org,
    days_in_future_to_predict,
    days_to_train,
    epochs,
    loss_function,
    optimizer_name,
    learning_rate,
    batch_size,
    early_stopping,
    stop_check,
    progress_callback,
    lstm_layers
):
    Status="OK"
    df = df_org.copy()
    scaler = MinMaxScaler(feature_range=(0, 1))
    scaled_data = scaler.fit_transform(df)

    X_train, X_test, y_train, y_test, X_pred = split_data(scaled_data, days_to_train, days_in_future_to_predict,df.columns.get_loc("Close"))

    # print("LSTM2")
    # print(f"X_train={X_train}")
    # print(f"X_test={X_test}")
    # print(f"y_train={y_train}")
    # print(f"y_test={y_test}")
    model = get_model(X_train.shape[1], X_train.shape[2],optimizer_name, learning_rate,loss_function,lstm_layers)

    best_val_loss = float('inf')
    patience = early_stopping
    no_improvement = 0
    loss = 0
    current_val_loss=0
    for epoch in range(epochs):
        if stop_check():
            Status =(f" User clicked Stop Training, stopped at epoch {epoch}")
            if epoch == 0:
                return None, None,None, Status
            break
        progress_callback("I am in LSTM2",epoch, epochs,loss, current_val_loss)
        train_effect=model.fit(
            X_train,
            y_train,
            epochs=1,
            batch_size=batch_size,
        )
        loss=train_effect.history['loss'][0]
        # tmp_X_test = X_test.copy()
        # div=0
        # for i in range(0, X_test.shape[0]):
        #     for j in range(i, i+days_in_future_to_predict):
        #         pred = model.predict(tmp_X_test[j].reshape(1, days_to_train, df.shape[1]))
        #         current_val_loss = current_val_loss + get_score(inverse_scaller(pred,df,scaler), y_test[j], loss_function, scaler,df)
        #         tmp_X_test[j] =np.roll(tmp_X_test[j], -1, axis=0)
        #         tmp_X_test[j][-1] = pred
        #         div = div+1
        # current_val_loss = current_val_loss / div
        tmp_X_test = X_test.copy()
        tmp_X_test.reshape(1,days_to_train, df.shape[1])
        current_val_loss=0

        result_of_testing = get_pred(model, X_test, days_to_train, df, days_in_future_to_predict)
        result_of_testing=result_of_testing.flatten()
        
        current_val_loss =get_score(result_of_testing, y_test, loss_function)

        if current_val_loss < best_val_loss:
            best_val_loss = current_val_loss
            no_improvement = 0
            model.save_weights('saved_weights/best_model.weights.h5')
        else:
            no_improvement += 1
    
        if no_improvement >= patience:
            Status=(f"Early stopping at epoch {epoch}")
            model.load_weights('saved_weights/best_model.weights.h5')
            break

    test_predictions = get_pred(model, X_test, days_to_train, df, days_in_future_to_predict)
    test_predictions = inverse_scaller(test_predictions, df, scaler)


    future_predictions = get_pred(model, X_pred, days_to_train, df, days_in_future_to_predict)
    future_predictions=inverse_scaller(future_predictions, df, scaler)

    real = inverse_scaller(y_test[-days_in_future_to_predict:], df_org, scaler)
    score = get_score(test_predictions,real,loss_function)

    return (test_predictions, future_predictions,score, Status)

############################# functions

def split_data(df, days_to_train,future_days,close_index):
    X_train = []
    y_train = []
    X_test = []
    y_test = []
    for i in range(days_to_train, len(df)-future_days-days_to_train+1):
        X_train.append(df[i - days_to_train : i])
        y_train.append(df[i, close_index])

    
    X_test.append(df[len(df) - days_to_train - future_days: len(df)-future_days])
    for i in range(future_days, 0, -1):
        y_test.append(df[-i,close_index] )

    X_train=np.array(X_train)
    y_train=np.array(y_train)

    X_test=np.array(X_test)
    y_test=np.array(y_test)


    X_train = X_train.reshape((X_train.shape[0], days_to_train, df.shape[1]))
    X_test = X_test.reshape((X_test.shape[0], days_to_train, df.shape[1]))
    y_train = y_train.reshape((y_train.shape[0], 1, 1))
    y_test = y_test.reshape((y_test.shape[0], 1))
    
    X_pred = [df[-days_to_train:]]
    X_pred=np.array(X_pred)
    X_pred = X_pred.reshape((X_pred.shape[0], days_to_train, df.shape[1]))
 

    return X_train, X_test, y_train, y_test, X_pred



def get_model(input_shape1, input_shape2, optimizer_name, learning_rate, loss_function ,lstm_layers):
    model = Sequential()
    
    for i, layer_config in enumerate(lstm_layers):
        if i == 0:
            model.add(LSTM(
                units=layer_config['units'],
                return_sequences=(i != len(lstm_layers) - 1),
                activation=layer_config['activation'],
                recurrent_activation=layer_config['recurrent_activation'],
                recurrent_dropout=layer_config['recurrent_dropout'],
                input_shape=(input_shape1, input_shape2)
            ))
        else:
            model.add(LSTM(
                units=layer_config['units'],
                return_sequences=(i != len(lstm_layers) - 1),
                activation=layer_config['activation'],
                recurrent_activation=layer_config['recurrent_activation'],
                recurrent_dropout=layer_config['recurrent_dropout']
            ))
        
        if i < len(lstm_layers) - 1:
            model.add(Dropout(layer_config['dropout']))
    
    model.add(Dense(units=1))
    opt = get_optimizer(optimizer_name, learning_rate)
    model.compile(optimizer=opt, loss=loss_function)
    model.summary()
    
    return model


def inverse_scaller(predictions, df, scaler):
    temp_array = np.zeros((predictions.shape[0], df.shape[1]))
    temp_array[:, df.columns.get_loc("Close")] = predictions.flatten()
    predictions_original = scaler.inverse_transform(temp_array)
    predictions_close = predictions_original[:, df.columns.get_loc("Close")]
    return predictions_close



def get_optimizer(name, learning_rate):
    if name == "adam":
        return Adam(learning_rate=learning_rate)
    elif name == "rmsprop":
        return RMSprop(learning_rate=learning_rate)
    elif name == "sgd":
        return SGD(learning_rate=learning_rate)
    
def get_score(predicted, real, loss_function):
    if loss_function == "mse":
        score = mean_squared_error(predicted, real)
    elif loss_function == "mae":
        score = mean_absolute_error(predicted, real)
    return score
    
def get_pred(model, X_pred, days_to_train, df, days_in_future ):
    result = []
    for i in range(0,days_in_future):
        pred = model.predict(X_pred.reshape(1, days_to_train, df.shape[1]))
        X_pred =np.roll(X_pred, -1, axis=0)
        X_pred[-1] = pred
        result.append(pred)
    return np.array(result)
