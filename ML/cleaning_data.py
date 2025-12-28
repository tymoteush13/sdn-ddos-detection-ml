import pandas as pd
import numpy as np
from pathlib import Path

DATA_DIR = Path("/home/tymek/Desktop/project/data")
pattern = "FlowStatsfile_*.csv"
NEGATIVE_LOG_FILE = DATA_DIR / "negative_values_log.csv"

negative_log = []

def clean_flowstats_file(filepath):

    df = pd.read_csv(filepath)
    df.columns = [c.strip() for c in df.columns]

    print(f"Początkowa liczba rekordów: {len(df)}")
    print(f"Kolumny początkowe: {list(df.columns)}")

    # Usuwanie zbędnych kolumn
    drop_cols = ["switch", "src", "dst", "port_no", "Pairflow", "dur_nsec", "dt", "flows","ip_proto"]
    drop_cols_analysis = ["switch", "src", "dst", "port_no", "Pairflow", "dur_nsec", "dt", "flows"]
    df_analysis = df.drop(columns=[c for c in drop_cols_analysis if c in df.columns], errors="ignore")

    removed = [c for c in drop_cols if c in df.columns]
    df.drop(columns=removed, inplace=True, errors="ignore")
    if removed:
        print(f"Usunięto kolumny: {removed}")
    else:
        print("Nie znaleziono kolumn do usunięcia.")

    # Czyszczenie wartości
    inf_count = np.isinf(df.select_dtypes(include=[np.number])).sum().sum()
    nan_count = df.isna().sum().sum()

    # Korygowanie wartości nieskończonych i uzupełnianie braków danych
    if inf_count > 0 or nan_count > 0:
        print(f"Znaleziono {inf_count} inf i {nan_count} NaN")
        df.replace([np.inf, -np.inf], np.nan, inplace=True)
        df.fillna(0, inplace=True)
    else:
        print("Brak wartości inf i NaN.")

    numeric_cols = df.select_dtypes(include=[np.number]).columns
    neg_mask = (df[numeric_cols] < 0).any(axis=1)
    neg_rows = df[neg_mask]

    if not neg_rows.empty:
        print(f"Znaleziono {len(neg_rows)} rekordów z wartościami ujemnymi.")
        neg_rows = df[neg_mask].copy()
        neg_rows["source_file"] = filepath.name
        negative_log.append(neg_rows.copy())
        for col in numeric_cols:
            df[col] = np.where(df[col] < 0, 0, df[col])
    else:
        print("Brak wartości ujemnych.")

    print(f"Liczba kolumn po czyszczeniu: {len(df.columns)}")
    print(f"Kolumny końcowe: {list(df.columns)}")
    print(f"Rekordów po czyszczeniu: {len(df)}")

    # Aplikowanie tych samych reguł czyszczących dla wersji analitycznej
    df_analysis = df_analysis.replace([np.inf, -np.inf], np.nan).fillna(0)
    numeric_cols_analysis = df_analysis.select_dtypes(include=[np.number]).columns
    for col in numeric_cols_analysis:
        df_analysis[col] = np.where(df_analysis[col] < 0, 0, df_analysis[col])

    return df,df_analysis

# Wczytanie i zapisanie każdego pliku osobno
all_files = list(DATA_DIR.glob(pattern))
if not all_files:
    print("Nie znaleziono plików w folderze.")
    exit()

print(f"Znaleziono {len(all_files)} plików do przetworzenia.\n")

for file in all_files:
    try:
        df_clean, df_analysis = clean_flowstats_file(file)

        output_path = DATA_DIR / f"cleaned_{file.name}"
        df_clean.to_csv(output_path, index=False)

        analysis_path = DATA_DIR / f"cleaned_analysis_{file.name}"
        df_analysis.to_csv(analysis_path, index=False)

        print(f"Zapisano:")
        print(f"  → ML:       {output_path}")
        print(f"  → Analiza:  {analysis_path}")
    except Exception as e:
        print(f"Błąd podczas przetwarzania {file.name}: {e}")

# Zapisanie wszystkich rekordow z wartościami ujemnymi
if negative_log:
    neg_df = pd.concat(negative_log, ignore_index=True)
    neg_df.to_csv(NEGATIVE_LOG_FILE, index=False)
    print(f"\nZapisano log rekordów z wartościami ujemnymi: {NEGATIVE_LOG_FILE}")
    print(f"Łączna liczba zapisanych rekordów: {len(neg_df)}")
else:
    print("\nNie znaleziono żadnych rekordów z wartościami ujemnymi.")

print("\nZakończono czyszczenie wszystkich plików.")
