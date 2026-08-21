import numpy as np
import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers
import pandas as pd
from sklearn.ensemble import RandomForestRegressor, ExtraTreesRegressor, GradientBoostingRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score
from sklearn.metrics import mean_squared_error, r2_score
from sklearn.preprocessing import StandardScaler, RobustScaler, MinMaxScaler, QuantileTransformer
from sklearn.model_selection import GroupShuffleSplit
from xgboost import XGBRegressor

def calculate_accuracy(model, X_test, y_test):
    y_pred=model.predict(X_test)
    score=r2_score(y_test, y_pred)
    mean_error=pow(mean_squared_error(y_test, y_pred),0.5)
    return score, mean_error

def group_split(df, X, y):
DS_CSV="data/metrics-20260630-out.csv"
    gss = GroupShuffleSplit(
        n_splits=1,
        test_size=0.3,
        random_state=42
    )
    train_idx, test_idx = next(
        gss.split(X, y, groups=df['local'])
    )
    X_train = X.iloc[train_idx]
    X_test = X.iloc[test_idx]
    y_train = y.iloc[train_idx]
    y_test = y.iloc[test_idx]
    return X_train, X_test, y_train, y_test
#DS_CSV="data/metrics-20260630-5g-out.csv"

df = pd.read_csv(DS_CSV, sep=',', header=0)
TARGTES = ['speedtest_down_mbps', 'speedtest_up_mbps', 'latency_ms', 'jitter_ms']


    #df=df.drop(columns=['speedtest_down_mbps', 'speedtest_up_mbps', '_time'])
    features=df.columns
    features=["router_expected_throughput_mbps",
              "router_noise",
              "router_rx_drop_misc",
              "router_rx_duration_us",
              "router_rx_rate_mbps",
              "router_signal_avg_dbm",
              "router_signal_dbm",
              "router_snr",
              "router_tx_duration_us",
              "router_tx_failed",
              "router_tx_rate_mbps",
              "router_tx_retries",
              "router_opportunity_medium_use",
              "client_opportunity_medium_use"]
    X = df[features]
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.3, random_state=42)
    #X_train, X_test, y_train, y_test = group_split(df, X, y)

    scaler = RobustScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    clf = RandomForestRegressor(n_estimators=600)
    history=clf.fit(X_train, y_train)
    model_score = clf.score(X_test, y_test)
    score, mean_error = calculate_accuracy(clf, X_test, y_test)
    print(f"-------------------------------------------------------------")
    print(f"RandomForestRegressor for {target}: Score={score}, Mean error={mean_error}")
    print(f"-------------------------------------------------------------")

    xgb = XGBRegressor(
        n_estimators=1000,
        learning_rate=0.03,
        max_depth=6,
        min_child_weight=3,
        subsample=0.8,
        colsample_bytree=0.8,
        reg_alpha=0.01,
        reg_lambda=1.0,
        objective="reg:squarederror",
        random_state=42
    )

    xgb.fit(
        X_train,
        y_train,
        eval_set=[(X_test, y_test)],
        verbose=False
    )

    y_pred = xgb.predict(X_test)
    score = xgb.score(X_test, y_test)
    mean_error=pow(mean_squared_error(y_test, y_pred),0.5)
    print(f"-------------------------------------------------------------")
    print(f"XGBRegressor for {target}: Score={score}, Mean error={mean_error}")
    print(f"-------------------------------------------------------------")

    from sklearn.tree import DecisionTreeRegressor
    melbourne_model = DecisionTreeRegressor(random_state=1)
    melbourne_model.fit(X_train, y_train)
    score, mean_error = calculate_accuracy(melbourne_model, X_test, y_test)
    print(f"-------------------------------------------------------------")
    print(f"DecisionTreeRegressor for {regression}: Score={score}, Mean error={mean_error}")
    print(f"-------------------------------------------------------------")
    model = keras.Sequential([
        # Input layer matching our features
        layers.Input(shape=(X_train.shape[1],)), 
        # Hidden layers with ReLU to capture non-linear relationships
        layers.Dense(2176, activation='relu'),
        layers.Dense(1088, activation='relu'),
        # Output layer: 1 unit with NO activation for continuous values
        layers.Dense(1)
    ])
    model.compile(
        optimizer='adam',
        loss='mean_squared_error',      # Standard loss for regression
        metrics=['mean_absolute_error'] # Easy to interpret error metric
    )
    history = model.fit(
        X_train_scaled, y_train,
        validation_split=0.2,           # Use 20% of data for validation
        epochs=50,
        batch_size=32,
        verbose=1
    )

    test_loss, test_mae = model.evaluate(X_test_scaled, y_test)
    #y_pred=model.predict(X_test[:34])
    score, mean_error = calculate_accuracy(model, X_test_scaled, y_test)
    print(f"-------------------------------------------------------------")
    print(f"Sequential Regressor for {regression}: Score={score}, Mean error={mean_error}")
    print(f"-------------------------------------------------------------")
    import matplotlib.pyplot as plt

    # Plotar acurácia
    plt.plot(history.history['mean_absolute_error'], label='Treino')
    plt.plot(history.history['val_mean_absolute_error'], label='Validação')
    plt.title('Error durante o treinamento')
    plt.xlabel('Épocas')
    plt.ylabel('Error')
    plt.legend()
    plt.show()

    # Plotar perda
    plt.plot(history.history['loss'], label='Treino')
    plt.plot(history.history['val_loss'], label='Validação')
    plt.title('Perda durante o treinamento')
    plt.xlabel('Épocas')
    plt.ylabel('Perda')
    plt.legend()
    plt.show()
