## 📋 Dataset Attributes

| **Attribute**              | **Description**                                                        | **Unit**              | **Type**                               |
| -------------------------- | ---------------------------------------------------------------------- | --------------------- | -------------------------------------- |
| **ID**                     | Unique identifier of DHN                                               | -                     | *str*                                  |
| **GEN**                    | Geographical name of administrative area                               | -                     | *str*                                  |
| **ARS**                    | Regional key of administrative area                                    | -                     | *str*                                  |
| **LAN**                    | State (Bundesland)                                                     | -                     | *str*                                  |
| **geometry**               | Polygon of presumed DHN                                                | EPSG:3035 Coordinates | *Polygon*                              |
| **area**                   | Area of presumed DHN                                                   | km²                   | *float*                                |
| **centroid**               | Centroid of presumed DHN                                               | EPSG:3035 Coordinates | *Point (WKT)*                          |
| **DH_demand**              | District heating annual demand of private households                   | MWh/year              | *float*                                |
| **total_demand_cells**     | Total annual heat demand of private households in cells with DH demand | MWh/year              | *float*                                |
| **total_demand_area**      | Total annual heat demand in area of presumed DHN                       | MWh/year              | *float*                                |
| **share_DH**               | Share of DH demand in area of presumed DHN                             | %                     | *float*                                |
| **heat_density_DH**        | DH_demand divided by area                                              | GWh/year/km²          | *float*                                |
| **heat_density**           | total_demand_area divided by area                                      | GWh/year/km²          | *float*                                |
| **DH_supplied_households** | Households supplied by DHN                                             | -                     | *int*                                  |
| **DH_cells**               | Cells that contain DH demand and form DHN area                         | EPSG:3035 Coordinates | *list of [int, int] (JSON serialized)* |