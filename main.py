import json
from typing import List, Union
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI()


class County(BaseModel):
    county: str
    state: str
    fips: str
    stateAbbrev: str
    fips: str


class SearchInput(BaseModel):
    county: str | None = None
    state: str | None = None


#####################################
#               LOGIC               #
#####################################


def normalize_county(county: str, is_louisiana: bool = False) -> str:
    cased = county.upper()
    ends_with_county = cased.endswith(" COUNTY")
    ends_with_parish = cased.endswith(" PARISH")

    if not ends_with_county and not ends_with_parish:
        if is_louisiana:
            return cased.strip() + " PARISH"
        else:
            return cased.strip() + " COUNTY"

    return cased


def get_counties_by_state(state: str) -> Union[List[County], str]:
    print("get_counties_by_state")
    normalized_state = state.upper()
    state_counties = []
    with open("fips_list.json") as file:
        counties = json.load(file)

        for county in counties:
            if county["state"] == normalized_state:
                state_counties.append(county)

    if not state_counties:
        raise HTTPException(status_code=404, detail="No results found")

    return state_counties


def get_counties_by_name(name: str) -> Union[List[County], str]:
    print("get_counties_by_name")
    normalized_county = normalize_county(name)
    state_counties = []
    with open("fips_list.json") as file:
        counties = json.load(file)

        for county in counties:
            if county["county"] == normalized_county:
                state_counties.append(county)

    if not state_counties:
        raise HTTPException(status_code=404, detail="No results found")

    return state_counties


def get_county_by_state_and_name(state: str, county_name: str) -> Union[County, str]:
    print("get_county_by_state_and_name")
    if not county_name or not state:
        return "Please provide a county name and state"

    normalized_state = state.upper()
    normalized_county = normalize_county(county_name, state == "LOUSIANA")

    with open("fips_list.json") as file:
        counties = json.load(file)

        for county in counties:
            if (
                county["state"] == normalized_state
                and county["county"] == normalized_county
            ):
                return county

    raise HTTPException(status_code=404, detail="No results found")


#####################################
#              ROUTES               #
#####################################


@app.get("/api/v2/index")
def get_all_counties() -> List[County]:
    with open("fips_list.json") as file:
        counties = json.load(file)

        all_counties = []

        for county in counties:
            all_counties.append(county)

        return all_counties


@app.get("/api/v2/search")
def county_search(input: SearchInput):
    if not input.state and not input.county:
        raise HTTPException(
            status_code=400, detail="Invalid request: missing search parameters"
        )
    elif input.state and not input.county:
        return get_counties_by_state(input.state)
    elif input.county and not input.state:
        return get_counties_by_name(input.county)
    elif input.state and input.county:
        return get_county_by_state_and_name(input.state, input.county)
