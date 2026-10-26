"""Pydantic models and controlled vocabularies for the Campus Customs shop."""

from __future__ import annotations

from enum import Enum


class GarmentType(str, Enum):
    """Allowed values for catalogue.garment_type (same labels as HW3's ItemType)."""

    t_shirt = "t-shirt"
    long_sleeve_shirt = "long-sleeve shirt"
    polo_shirt = "polo shirt"
    crewneck_sweatshirt = "crewneck sweatshirt"
    hooded_sweatshirt = "hooded sweatshirt"
    full_zip_hooded_sweatshirt = "full-zip hooded sweatshirt"
    quarter_zip_pullover = "quarter-zip pullover"
    mock_neck_pullover = "mock-neck pullover"
    sweater = "sweater"
    fleece_jacket = "fleece jacket"
    jacket = "jacket"
    other = "other"


# Shopper-facing label for each type, in the order the shop's browse menu lists them.
GARMENT_TYPE_LABELS: dict[GarmentType, str] = {
    GarmentType.t_shirt: "T-Shirts",
    GarmentType.long_sleeve_shirt: "Long-Sleeve Shirts",
    GarmentType.polo_shirt: "Polos",
    GarmentType.crewneck_sweatshirt: "Crewneck Sweatshirts",
    GarmentType.hooded_sweatshirt: "Hoodies",
    GarmentType.full_zip_hooded_sweatshirt: "Full-Zip Hoodies",
    GarmentType.quarter_zip_pullover: "Quarter-Zips",
    GarmentType.mock_neck_pullover: "Mock-Necks",
    GarmentType.sweater: "Sweaters",
    GarmentType.fleece_jacket: "Fleece Jackets",
    GarmentType.jacket: "Jackets",
    GarmentType.other: "Other",
}


class Color(str, Enum):
    """Standard color names for catalogue.primary_color and catalogue.accent_colors."""

    navy = "navy"
    blue = "blue"
    light_blue = "light blue"
    heather_gray = "heather gray"
    charcoal_gray = "charcoal gray"
    light_gray = "light gray"
    gray = "gray"
    white = "white"
    cream = "cream"
    black = "black"
    red = "red"
    coral = "coral"
    green = "green"
    gold = "gold"
    yellow = "yellow"
    multicolor = "multicolor"


# Clothing sizes, smallest first.
SIZES: list[str] = ["XS", "S", "M", "L", "XL", "XXL"]
