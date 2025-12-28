import pandas as pd
import numpy as np
from pathlib import Path
from sklearn.neighbors import KNeighborsClassifier
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score,
    f1_score, confusion_matrix, classification_report
)
from sklearn.model_selection import cross_val_score
from sklearn.preprocessing import StandardScaler
import matplotlib.pyplot as plt
import seaborn as sns
from imblearn.over_sampling import SMOTE
from sklearn.metrics import pairwise_distances

PLOTS_DIR = Path("/home/tymek/Desktop/project/plots")
PLOTS_DIR.mkdir(exist_ok=True)

def save_current_plot(name: str):
    out_path = PLOTS_DIR / f"k-NN_{name}.png"
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

# Korelacje między cechami
corr_matrix = X_train.corr()

plt.figure(figsize=(14, 12))
sns.heatmap(corr_matrix, cmap="coolwarm", center=0, square=True,
            cbar_kws={"shrink": 0.8}, linewidths=0.1)
plt.title("Macierz korelacji cech (X_train)")
plt.tight_layout()
save_current_plot("correlation_matrix")

# Silne korelacje
threshold = 0.9
high_corr_pairs = (
    corr_matrix.where(np.triu(np.ones(corr_matrix.shape), k=1).astype(bool))
    .stack()
    .reset_index()
)
high_corr_pairs.columns = ['Cecha_1', 'Cecha_2', 'Korelacja']
high_corr_pairs = high_corr_pairs.loc[high_corr_pairs['Korelacja'].abs() > threshold]

print("\n Silnie skorelowane pary cech (|r| > 0.9):")
print(high_corr_pairs.sort_values(by='Korelacja', ascending=False))

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
scaler = StandardScaler()
X_train_bal_scaled = scaler.fit_transform(X_train_bal)
X_test_scaled = scaler.transform(X_test)
print(" Dane znormalizowane (StandardScaler).")

subset_size = 1000
rng = np.random.default_rng(42)
idx = rng.choice(len(X_train_bal_scaled), size=subset_size, replace=False)

X_sub = X_train_bal_scaled[idx]
y_sub = np.array(y_train_bal)[idx]

# Obliczanie macierzy odległości euklidesowych
dist_matrix = pairwise_distances(X_sub, metric='euclidean')

same_class = (y_sub[:, None] == y_sub[None, :])
diff_class = ~same_class

intra_dist = dist_matrix[same_class]
inter_dist = dist_matrix[diff_class]

print(f" Średnia odległość wewnątrzklasowa: {np.mean(intra_dist):.4f}")
print(f" Średnia odległość międzyklasowa:   {np.mean(inter_dist):.4f}")

ratio = np.mean(inter_dist) / np.mean(intra_dist)
print(f" Stosunek międzyklasowa / wewnątrzklasowa = {ratio:.2f}")

# Wykres porównawczy
plt.figure(figsize=(6,4))
plt.bar(['Wewnątrzklasowa', 'Międzyklasowa'], [np.mean(intra_dist), np.mean(inter_dist)],
        color=['skyblue', 'orange'])
plt.title("Średnie odległości w przestrzeni cech")
plt.ylabel("Odległość euklidesowa (średnia)")
plt.tight_layout()
save_current_plot("feature_space_distances")

clf = KNeighborsClassifier(
    n_neighbors=7,       # liczba sąsiadów
    weights="distance",  # waga odwrotna do odległości
    n_jobs=-1
)

# Walidacja krzyżowa
scores = cross_val_score(clf, X_train_bal_scaled, y_train_bal, cv=5, scoring="f1")
print(f"\n Średni F1-score (5-fold CV): {scores.mean():.4f} ± {scores.std():.4f}")

print("\n Trening modelu k-NN...")
clf.fit(X_train_bal_scaled, y_train_bal)

# Predykcja
y_pred = clf.predict(X_test_scaled)

# Metryki jakości
acc = accuracy_score(y_test, y_pred)
prec = precision_score(y_test, y_pred, pos_label=1)
rec = recall_score(y_test, y_pred, pos_label=1)
f1 = f1_score(y_test, y_pred, pos_label=1)

print("\n Wyniki modelu k-NN:")
print(f" Accuracy:  {acc:.4f}")
print(f" Precision: {prec:.4f}")
print(f" Recall:    {rec:.4f}")
print(f" F1-score:  {f1:.4f}")

print("\n Pełny raport klasyfikacji:")
print(classification_report(y_test, y_pred, target_names=["Ruch normalny", "Atak"], digits=4))

# Macierz pomyłek
cm = confusion_matrix(y_test, y_pred)
plt.figure(figsize=(6, 5))
sns.heatmap(cm, annot=True, fmt="d", cmap="Blues",
            xticklabels=["Ruch normalny", "Atak"], yticklabels=["Ruch normalny", "Atak"])
plt.title("Macierz pomyłek — k-NN")
plt.ylabel("Rzeczywista klasa")
plt.xlabel("Przewidziana klasa")
plt.tight_layout()
save_current_plot("confusion_matrix")
