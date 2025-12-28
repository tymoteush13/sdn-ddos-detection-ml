import pandas as pd
from pathlib import Path

DATA_DIR = Path("/home/tymek/Desktop/project/data")
pattern = "cleaned_FlowStatsfile_*.csv"

TARGET_ATTACK_SAMPLES = 50000  # liczba rekordów (downsampling)

train_dfs = []
test_dfs = []

for file in DATA_DIR.glob(pattern):

    df = pd.read_csv(file)

    zero_mask = (
        (df["delta_pkts"] == 0) &
        (df["delta_bytes"] == 0) &
        (df["dpktrate"] == 0) &
        (df["dbytrate_Bps"] == 0) &
        (df["byte_per_pkt"] == 0)
    )
    removed = zero_mask.sum()
    # Eliminowanie przepływów o zerowej dynamice
    df = df[~zero_mask]

    print(f" Usunięto {removed} flowów z deltą = 0 ({removed / (removed + len(df)) * 100:.2f}%).")

    # Rozpoznawanie typu ruchu po nazwie pliku
    name = file.name.lower()

    if "udp" in name or "tcp-syn" in name:
        df_sampled = df.sample(min(len(df), TARGET_ATTACK_SAMPLES), random_state=42)

    else:
        df_sampled = df.copy()

    # Podział 75/25
    split_idx = int(len(df_sampled) * 0.75)
    train_dfs.append(df_sampled.iloc[:split_idx])
    test_dfs.append(df_sampled.iloc[split_idx:])

train_balanced = pd.concat(train_dfs, ignore_index=True)
test_balanced = pd.concat(test_dfs, ignore_index=True)

# Eksportowanie gotowych zbiorów do plików CSV
train_balanced.to_csv(DATA_DIR / "train_balanced.csv", index=False)
test_balanced.to_csv(DATA_DIR / "test_balanced.csv", index=False)

print("\n Zrównoważone dane zapisane:")
print("→ train_balanced.csv")
print("→ test_balanced.csv")
print(f"\n Rozmiar nowego train: {len(train_balanced)}")
print(f" Rozmiar nowego test:  {len(test_balanced)}")
