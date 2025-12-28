import pandas as pd
import numpy as np
from pathlib import Path
from sklearn.svm import LinearSVC
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score,
    f1_score, confusion_matrix, classification_report
)
from sklearn.model_selection import cross_val_score
import matplotlib.pyplot as plt
import seaborn as sns
from imblearn.over_sampling import SMOTE
from sklearn.preprocessing import StandardScaler
# from sklearn.model_selection import GridSearchCV
# from sklearn.model_selection import StratifiedKFold, learning_curve
# from sklearn.exceptions import FitFailedWarning
# import warnings

PLOTS_DIR = Path("/home/tymek/Desktop/project/plots")
PLOTS_DIR.mkdir(exist_ok=True)

def save_current_plot(name: str):
    out_path = PLOTS_DIR / f"SVM_{name}.png"
    plt.savefig(out_path, dpi=300, bbox_inches="tight")
    plt.close()

# Wczytywanie danych
DATA_DIR = Path("/home/tymek/Desktop/project/data")
train_df = pd.read_csv(DATA_DIR / "train_balanced.csv")
test_df = pd.read_csv(DATA_DIR / "test_balanced.csv")

print("Dane treningowe:", train_df.shape)
print("Dane testowe:", test_df.shape)

# Przygotowanie danych
X_train = train_df.drop(columns=["label"])
y_train = train_df["label"]

X_test = test_df.drop(columns=["label"])
y_test = test_df["label"]

# Usuwanie kolumn o zerowej wariancji
constant_cols = [c for c in X_train.columns if X_train[c].nunique() <= 1]
if constant_cols:
    X_train = X_train.drop(columns=constant_cols)
    X_test = X_test.drop(columns=constant_cols, errors="ignore")

# Usuwanie nienumerycznych kolumn
X_train = X_train.select_dtypes(include=["number"])
X_test = X_test.select_dtypes(include=["number"])

# Logarytmizacja cech
log_cols = [
    "pktcount", "bytecount", "delta_pkts", "delta_bytes",
    "dpktrate", "dbytrate_Bps", "byte_per_pkt",
    "tx_bytes", "rx_bytes", "tx_kbps", "rx_kbps", "tot_kbps"
]
for col in log_cols:
    if col in X_train.columns:
        X_train[col] = np.log1p(X_train[col])
        X_test[col] = np.log1p(X_test[col])

drop_features = [
    "tot_dur", "tot_kbps"
]

drop_features = [f for f in drop_features if f in X_train.columns]
if drop_features:
    X_train = X_train.drop(columns=drop_features)
    X_test = X_test.drop(columns=drop_features, errors="ignore")

# Balansowanie danych (SMOTE)
smote = SMOTE(sampling_strategy=0.33, random_state=42)
X_train_bal, y_train_bal = smote.fit_resample(X_train, y_train)
print(" Po SMOTE:", y_train_bal.value_counts().to_dict())

# Skalowanie
print("\n Skalowanie danych...")
scaler = StandardScaler()
X_train_bal = scaler.fit_transform(X_train_bal)
X_test_scaled = scaler.transform(X_test)
print(" Dane znormalizowane.")

clf = LinearSVC(
    C=1.0,
    class_weight={0: 3, 1: 1},
    max_iter=20000,
    loss="hinge",
    random_state=42
)

# # Dobieranie najlepszych parametrow
# param_grid = {
#     "C": [0.01, 0.1, 1, 5, 10, 50, 100],     # różne poziomy regularyzacji
#     "loss": ["hinge", "squared_hinge"],      # dwie geometrie marginesu
#     "class_weight": [
#         None,
#         {0:1, 1:1},
#         {0:2, 1:1},
#         {0:3, 1:1},
#         {0:4, 1:1},
#         {0:5, 1:1}
#     ]
# }

# grid = GridSearchCV(
#     LinearSVC(max_iter=20000, random_state=42),
#     param_grid=param_grid,
#     scoring="f1",
#     cv=3,
#     n_jobs=-1,
#     verbose=2
# )

# print("\n Najlepsze parametry:")
# print(grid.best_params_)

# clf = grid.best_estimator_

# Walidacja krzyżowa
scores = cross_val_score(clf, X_train_bal, y_train_bal, cv=5, scoring="f1")
print(f"\n Średni F1-score (5-fold CV): {scores.mean():.4f} ± {scores.std():.4f}")

print("\n Trening modelu Linear SVM...")
clf.fit(X_train_bal, y_train_bal)

# Predykcja
y_pred = clf.predict(X_test_scaled)

# Metryki jakości
acc = accuracy_score(y_test, y_pred)
prec = precision_score(y_test, y_pred, pos_label=1)
rec = recall_score(y_test, y_pred, pos_label=1)
f1 = f1_score(y_test, y_pred, pos_label=1)

print("\n Wyniki modelu Linear SVM:")
print(f" Accuracy:  {acc:.4f}")
print(f" Precision: {prec:.4f}")
print(f" Recall:    {rec:.4f}")
print(f" F1-score:  {f1:.4f}")

print("\n Pełny raport klasyfikacji:")
print(classification_report(y_test, y_pred, target_names=["Ruch normalny", "Atak"], digits=4))

# Macierz pomyłek
cm = confusion_matrix(y_test, y_pred)
plt.figure(figsize=(6,5))
sns.heatmap(cm, annot=True, fmt="d", cmap="Blues",
            xticklabels=["Ruch normalny", "Atak"], yticklabels=["Ruch normalny", "Atak"])
plt.title("Macierz pomyłek — Linear SVM")
plt.ylabel("Rzeczywista klasa")
plt.xlabel("Przewidziana klasa")
save_current_plot("confusion_matrix")
