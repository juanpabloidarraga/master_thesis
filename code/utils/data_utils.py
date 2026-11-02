# Example usage of the data_utils module for loading and processing the master catalog.
# from utils.data_utils import load_data, build_masks
#
# df_master = load_data()
# masks = build_masks(df_master)
# good_galah_mask = masks["good_galah"]


import pandas as pd
import numpy as np


def load_data(data_path: str = "../data/extra_catalogs/") -> pd.DataFrame:
    """
    Load the master dataframe from a CSV file.

    Returns:
        pd.DataFrame: The loaded master dataframe.
    """
    return pd.read_csv(data_path + "K2_Kepler_TESS_x_GALAH_LAMOST.csv")


def build_masks(df: pd.DataFrame) -> dict[str, pd.Series]:
    """Create reusable selection masks for any catalog."""
    masks = {

        # Galah data mask (also includes stars that are in both surveys)
        "galah": df["survey_match"].isin(
            ["galah", "both"]
        ),
        #Lamost data mask
        "lamost": df["survey_match"].eq("lamost"),
        #Good spectroscopy masks for GALAH
        "good_galah": (df["flag_sp"].eq(0) & df["snr_px_ccd3"].gt(30)),

        #Good spectroscopy masks for LAMOST ( Not sure about putting this here or with Li_good_lamost)
        "good_lamost": df["S_N_lamost"].gt(
            20
        ), 

        #Create masks for Willet data
        "k2": df["K2_campaign"].between(1, 199),
        "kepler": df["K2_campaign"].eq(0),
        "tess": df["K2_campaign"].gt(200),

        # Definition of what is good or bad taken from Willet et al 2024
        #TODO define "goodK2_mask", "goodKepler_mask", "goodTESS_mask"
    }


    # Combining masks for good spectroscopy
    masks["good_galah_galah"] = masks["galah"] & masks["good_galah"]
    masks["good_lamost_lamost"] = masks["lamost"] & masks["good_lamost"]
    masks["good_spectroscopy"] = masks["good_galah"] | masks["good_lamost"]

    #Mask for good temperature data
    masks["t_good_galah"] = masks["good_galah_galah"] & df["teff"].notna()
    masks["t_good_lamost"] = masks["good_lamost_lamost"] & df["Teff_lamost"].notna()

    # Mask for kepler and evolutionary state
    masks["rgb_kepler"] = df["EvoState"].eq(1)
    masks["rc_kepler"] = df["EvoState"].eq(2)
    

    masks["li_good_galah"] = masks["good_galah_galah"] & df["flag_a_li"].eq(False)
    masks["li_good_lamost"] = masks["good_lamost_lamost"] & df["Lim"].eq(0)

    return masks


def add_unified_columns(
    df: pd.DataFrame,
    masks: dict[str, pd.Series],
) -> pd.DataFrame:
    """Add unified columns for metallicity and effective temperature to the dataframe."""
    df = add_unified_metallicity(df, masks)
    df = add_unified_temperature(df, masks)
    return df


def add_unified_metallicity(
    df: pd.DataFrame,
    masks: dict[str, pd.Series],
) -> pd.DataFrame:
    """Add a unified metallicity column to the dataframe."""
    # create new column for metallicity
    df["feh"] = np.nan
    # fill metallicity for GALAH and LAMOST
    df.loc[masks["galah"], "feh"] = pd.to_numeric(
        df.loc[masks["galah"], "fe_h_2"], errors="coerce"
    )
    df.loc[masks["lamost"], "feh"] = pd.to_numeric(
        df.loc[masks["lamost"], "__Fe_H_"], errors="coerce"
    )
    return df


def add_unified_temperature(
    df: pd.DataFrame,
    masks: dict[str, pd.Series],
) -> pd.DataFrame:
    """Add a unified effective temperature column to the dataframe."""
    # create new columns for effective temperature and its source
    df["teff"] = np.nan
    df["teff_source"] = ""

    # fill effective temperature and source for GALAH
    df.loc[masks["galah"], "teff"] = pd.to_numeric(
        df.loc[masks["galah"], "teff"], errors="coerce"
    )
    df.loc[masks["galah"], "teff_source"] = "GALAH"

    # fill effective temperature and source for LAMOST
    df.loc[masks["lamost"], "teff"] = pd.to_numeric(
        df.loc[masks["lamost"], "Teff_lamost"], errors="coerce"
    )
    df.loc[masks["lamost"], "teff_source"] = "LAMOST"
    return df


def create_survey_catalog(
    df: pd.DataFrame,
    mask: pd.Series,
) -> pd.DataFrame:
    """
    Return a copy containing only rows selected by mask.
    The function is to avoid repeating the same code for each survey catalog creation: df_master.loc[masks["some_mask"]].copy()
    """
    return df.loc[mask].copy()


def create_galah_catalog(
    df: pd.DataFrame,
    masks: dict[str, pd.Series],
) -> pd.DataFrame:
    """Create a catalog for the GALAH survey."""
    return create_survey_catalog(df, masks["galah"])


def create_lamost_catalog(
    df: pd.DataFrame,
    masks: dict[str, pd.Series],
) -> pd.DataFrame:
    """Create a catalog for the LAMOST survey."""
    return create_survey_catalog(df, masks["lamost"])


def create_kiel_sample(
    df: pd.DataFrame,
    masks: dict[str, pd.Series],
) -> pd.DataFrame:
    """Create a Kiel sample from the master catalog."""
    return create_survey_catalog(df, masks["good_spectroscopy"])


def create_lithium_sample(
    df: pd.DataFrame,
    masks: dict[str, pd.Series],
) -> pd.DataFrame:
    """Create a lithium sample from the master catalog."""
    return create_survey_catalog(df, masks["li_good_galah"] | masks["li_good_lamost"])


def validate_required_columns(
    df: pd.DataFrame,
    required_columns: list[str],
) -> None:
    """Validate that the required columns are present in the dataframe."""
    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        raise ValueError(f"Missing required columns: {missing_columns}")


def summarize_masks(
    masks: dict[str, pd.Series],
) -> pd.DataFrame:
    """
    Summarize the number and percentage of rows selected by each mask.
    This helps detect unexpected masks, for example a mask selecting zero rows or almost the entire catalog.
    """
    total_rows = len(next(iter(masks.values())))

    return pd.DataFrame(
        {
            "mask": masks.keys(),
            "selected_rows": [mask.sum() for mask in masks.values()],
            "total_rows": total_rows,
            "percentage": [mask.mean() * 100 for mask in masks.values()],
        }
    )
