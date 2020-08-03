import os
import requests
import pandas as pd


CUR_PATH = os.path.abspath(os.path.dirname(__file__))


def update_cpim(baseline):
    """
    Update the CPI-M values in the CBO baseline using the BLS API
    """
    print("Updating CPI-M Values")
    url = "https://api.bls.gov/publicAPI/v1/timeseries/data/CUSR0000SAM"
    # fetch BLS data from about url
    r = requests.get(url)
    # raise and error if the request fails
    assert r.status_code == 200
    result_json = r.json()
    # raise error if request was not successful
    assert result_json["status"] == "REQUEST_SUCCEEDED"
    # extract the data from the results
    data = result_json["Results"]["series"][0]["data"]
    df = pd.DataFrame(data)
    # convert the values to floats so that the groupby mean only returns
    # the mean for the value
    df["value"] = df["value"].astype(float)
    cpi_mean = df.groupby("year").mean().transpose().round(1)
    cpi_mean.index = ["CPIM"]

    # open the current baseline to replace the values for the years pulled
    # from BLS
    baseline.update(cpi_mean)

    # find the average difference between CPIM and CPIU for available years
    last_year = max(cpi_mean.columns)
    first_year = min(baseline.columns)
    # retrieve subset of the DataFrame containing actual CPIM values
    split_col = int(last_year) - int(first_year) + 1
    sub_baseline = baseline[baseline.columns[: split_col]]

    # find the difference
    mean_diff = (sub_baseline.loc["CPIM"] - sub_baseline.loc["CPIU"]).mean()

    # update the future values to reflect the difference between
    new_vals = {}
    for col in baseline.columns[split_col:]:
        cpiu = baseline[col].loc["CPIU"]
        new_val = cpiu + mean_diff
        new_vals[col] = [new_val]
    future_df = pd.DataFrame(new_vals, index=["CPIM"]).round(1)
    baseline.update(future_df)

    return baseline


def update_econproj(econ_url, cg_url, baseline):
    """
    Function that will read new CBO economic projections and update
    CBO_baseline.csv accordingly
    """
    print("Updating CBO Economic Proections")
    # read in economic projections
    econ_proj = pd.read_excel(econ_url, sheet_name="2. Calendar Year",
                              skiprows=6, index_col=[0, 1, 2, 3])
    # extract values for needed rows in the excel file
    # some variables have a missing value in the multi-index. Use iloc
    # to extract needed variables from them.
    gdp = econ_proj.loc["Output"].loc["Gross Domestic Product (GDP)"].iloc[0]
    income = econ_proj.loc["Income"]
    tpy = income.loc["Income, Personal"].iloc[0]
    wages = income.loc["Wages and Salaries"].iloc[0]
    billions = "Billions of dollars"
    var = "Proprietors' income, nonfarm, with IVA & CCAdj"
    schc = income.loc["Nonwage Income"].loc[var].loc[billions]
    var = "Proprietors' income, farm, with IVA & CCAdj"
    schf = income.loc["Nonwage Income"].loc[var].loc[billions]
    var = "Interest income, personal"
    ints = income.loc["Nonwage Income"].loc[var].loc[billions]
    var = "Dividend income, personal"
    divs = income.loc["Nonwage Income"].loc[var].loc[billions]
    var = "Income, rental, with CCAdj"
    rents = income.loc["Nonwage Income"].loc[var].loc[billions]
    book = income.loc["Profits, Corporate, With IVA & CCAdj"].iloc[0]
    var = "Consumer Price Index, All Urban Consumers (CPI-U)"
    cpiu = econ_proj.loc["Prices"].loc[var].iloc[0]

    # Extract capital gains data
    cg_proj = pd.read_excel(cg_url, sheet_name="6. Capital Gains Realizations",
                            skiprows=7, header=[0, 1])
    cg_proj.index = cg_proj[cg_proj.columns[0]]
    var = "Capital Gains Realizationsa"
    cgns = cg_proj[var]["Billions of Dollars"].loc[list(range(2017, 2031))]

    # create one DataFrame from all of the data

    var_list = [gdp, tpy, wages, schc, schf, ints, divs, rents, book, cpiu,
                cgns]
    var_names = ["GDP", "TPY", "Wages", "SCHC", "SCHF", "INTS", "DIVS",
                 "RENTS", "BOOK", "CPIU", "CGNS"]
    df = pd.DataFrame(var_list, index=var_names).round(1)
    df.columns = df.columns.astype(str)

    # update baseline file with the new data

    # add a column for any years that are in the update but not yet in the
    # CBO baseline file before updating the values
    df_cols = set(df.columns)
    baseline_cols = set(baseline.columns)
    for col in df_cols - baseline_cols:
        baseline[col] = None
    baseline.update(df)

    return baseline


def update_socsec(url, baseline):
    """
    Function that will read the table with OASI Social Security Projections
    """
    print("Updating Social Security Projections")
    match_txt = "Operations of the OASI Trust Fund, Fiscal Years"
    html = pd.read_html(url, match=match_txt)[0]
    # merge the columns with years and data into one
    sub_data = pd.concat(
        [
            html["Fiscal year", "Fiscal year.1"],
            html["Cost", "Sched-uled benefits"]
        ],
        axis=1
    )
    sub_data.columns = ["year", "cost"]
    # further slim down data so that we have the intermediate costs only
    start = sub_data.index[sub_data["year"] == "Intermediate:"][0]
    end = sub_data.index[sub_data["year"] == "Low-cost:"][0]
    cost_data = sub_data.iloc[start + 1: end].dropna()
    cost_data["cost"] = cost_data["cost"].astype(float)
    # rate we'll use to extrapolate costs to final year we'll need
    pct_change = cost_data["cost"].pct_change() + 1
    cost_data.set_index("year", inplace=True)
    cost_data = cost_data.transpose()
    cost_data.index = ["SOCSEC"]
    # create values for years not included in the report
    factor = pct_change.iloc[-1]
    last_year = int(max(cost_data.columns))
    cbo_last_year = int(max(baseline.columns))
    for year in range(last_year + 1, cbo_last_year + 1):
        cost_data[str(year)] = cost_data[str(year - 1)] * factor
    cost_data = cost_data.round(1)
    # finally update CBO projections
    baseline.update(cost_data)

    return baseline


def update_rets(url, baseline):
    """
    Update projected tax returns
    """
    print("updating Return Projections")
    data = pd.read_excel(
        url, sheet_name="1B-BOD", index_col=0, header=2
    )
    projections = data.loc["Forms 1040, Total*"]
    projections /= 1000000  # convert units
    pct_change = projections.pct_change() + 1
    # extrapolate out to final year of other CBO projections
    factor = pct_change.iloc[-1]
    last_year = int(max(projections.index))
    cbo_last_year = int(max(baseline.columns))
    df_projections = pd.DataFrame(projections).transpose()
    df_projections.columns = df_projections.columns.astype(str)
    for year in range(last_year + 1, cbo_last_year + 1):
        df_projections[str(year)] = df_projections[str(year - 1)] * factor
    df_projections.index = ["RETS"]
    df_projections = df_projections.round(1)
    baseline.update(df_projections)
    return baseline


def update_ucomp(url, baseline):
    """
    Update unemployment compensation projections
    """
    print("Updating Unemployment Projections")
    data = pd.read_excel(url, skiprows=3, index_col=0, thousands=",")
    benefits = data.loc['     Total benefits'].astype(int) / 1000
    benefits = benefits.round(1)
    df = pd.DataFrame(benefits).transpose()
    df.index = ["UCOMP"]
    df.columns = df.columns.astype(str)
    baseline.update(df)
    return baseline


def update_cbo():
    ECON_URL = "https://www.cbo.gov/system/files/2020-01/51135-2020-01-economicprojections_0.xlsx"
    CG_URL = "https://www.cbo.gov/system/files/2020-01/51138-2020-01-revenue-projections.xlsx"
    SOCSEC_URL = "https://www.ssa.gov/oact/TR/2019/VI_C_SRfyproj.html#306103"
    RETS_URL = "https://www.irs.gov/pub/irs-soi/19projpub6187tables.xls"
    UCOMP_URL = "https://www.cbo.gov/system/files/2020-01/51316-2020-01-unemployment.xlsx"
    baseline = pd.read_csv(os.path.join(CUR_PATH, "CBO_baseline.csv"),
                           index_col=0)
    baseline = update_econproj(ECON_URL, CG_URL, baseline)
    baseline = update_cpim(baseline)
    baseline = update_socsec(SOCSEC_URL, baseline)
    baseline = update_rets(RETS_URL, baseline)
    baseline = update_ucomp(UCOMP_URL, baseline)

    return baseline


if __name__ == "__main__":
    baseline = update_cbo()
    baseline.to_csv(os.path.join(CUR_PATH, "CBO_baseline.csv"))
    msg = ("NOTE: Remember to update the dates and links in"
           " CBO_Baseline_Updating_Instructions.md accordingly. ")
    print(msg)
