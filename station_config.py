"""
Per-station configuration for the Maitri / Bharati Digital Twin data generator.

Seasonal temperature/wind parameters are anchored to public historical data so the
synthetic ranges hold up if a judge probes realism (see Section 4 of the team
reference doc, "No real sensor data" risk). Sources noted inline; everything below
the climate block (power/fuel/logistics baselines) is a reasonable hackathon-scale
assumption, not measured data -- call this out explicitly in the pitch too.

Climate anchors:
  Maitri (Schirmacher Oasis, 70.76S 11.74E, ~100m ASL) -- continental/interior-leaning,
    wider swings. Annual mean ~-10.4C, summer mean ~+0.9C, winter mean ~-22C,
    extremes recorded -35.3C to +12.2C, annual mean wind ~9.7 m/s.
    (Schirmacher Oasis climatology; Lal 2021 short-period climatology of Maitri)
  Bharati (Larsemann Hills, 69.41S 76.19E, ~35m ASL) -- coastal, milder & less extreme
    than Maitri. Winter mean ~-18C, summer mean ~-5C to +3C, persistent katabatic
    winds, coldest month historically September, warmest January.
    (NCPOR synoptic data; Bharati station climatology reviews)
"""

from dataclasses import dataclass, field


@dataclass
class ClimateProfile:
    # Seasonal sinusoid: temp(day_of_year) = mean + amplitude * cos(2*pi*(doy-peak_doy)/365)
    annual_mean_c: float
    seasonal_amplitude_c: float          # half the summer-to-winter swing
    peak_warmth_doy: int                 # day-of-year of the warmest point (austral summer)
    diurnal_amplitude_c: float           # day/night wobble on top of the seasonal curve
    noise_std_c: float                   # short-term random-walk noise
    wind_mean_ms: float
    wind_std_ms: float
    storm_prob_per_hour: float           # chance/hour of a storm event kicking off


@dataclass
class PowerProfile:
    base_load_kw: float                  # baseline station electrical load
    load_diurnal_amplitude_kw: float      # daily activity cycle on top of base
    load_noise_std_kw: float
    n_generators: int
    generator_rated_kw: float
    battery_capacity_kwh: float
    fuel_tank_capacity_l: float
    fuel_tank_start_frac: float
    specific_fuel_consumption_l_per_kwh: float  # genset fuel burn per kWh produced


@dataclass
class StationConfig:
    station_id: str
    display_name: str
    location: str
    latitude: float
    longitude: float
    climate: ClimateProfile
    power: PowerProfile
    resupply_interval_days: int          # typical time between resupply windows
    resupply_window_open_doy: int        # day-of-year the annual resupply season opens


STATIONS: dict[str, StationConfig] = {
    "maitri": StationConfig(
        station_id="maitri",
        display_name="Maitri",
        location="Schirmacher Oasis, East Antarctica",
        latitude=-70.7660,
        longitude=11.7395,
        climate=ClimateProfile(
            annual_mean_c=-10.4,
            seasonal_amplitude_c=11.5,      # (-0.9C summer, -22C winter roughly)
            peak_warmth_doy=45,             # mid-February (austral summer peak)
            diurnal_amplitude_c=2.5,
            noise_std_c=0.6,
            wind_mean_ms=9.7,
            wind_std_ms=3.2,
            storm_prob_per_hour=0.01,
        ),
        power=PowerProfile(
            base_load_kw=55.0,
            load_diurnal_amplitude_kw=8.0,
            load_noise_std_kw=2.0,
            n_generators=3,
            generator_rated_kw=125.0,
            battery_capacity_kwh=400.0,
            fuel_tank_capacity_l=200_000.0,
            fuel_tank_start_frac=0.82,
            specific_fuel_consumption_l_per_kwh=0.28,
        ),
        resupply_interval_days=330,
        resupply_window_open_doy=335,       # ~end Nov / summer resupply season
    ),
    "bharati": StationConfig(
        station_id="bharati",
        display_name="Bharati",
        location="Larsemann Hills, East Antarctica",
        latitude=-69.4080,
        longitude=76.1874,
        climate=ClimateProfile(
            annual_mean_c=-8.0,
            seasonal_amplitude_c=9.5,       # (~+1C summer, -18C winter roughly)
            peak_warmth_doy=20,             # January warmest historically
            diurnal_amplitude_c=1.8,        # coastal -> smaller diurnal swing than Maitri
            noise_std_c=0.5,
            wind_mean_ms=8.2,
            wind_std_ms=3.8,                # katabatic gusts -> more variance
            storm_prob_per_hour=0.014,
        ),
        power=PowerProfile(
            base_load_kw=48.0,
            load_diurnal_amplitude_kw=7.0,
            load_noise_std_kw=1.8,
            n_generators=3,                 # 3 diesel-fired CHP units (NCPOR docs)
            generator_rated_kw=110.0,
            battery_capacity_kwh=350.0,
            fuel_tank_capacity_l=180_000.0,
            fuel_tank_start_frac=0.78,
            specific_fuel_consumption_l_per_kwh=0.27,
        ),
        resupply_interval_days=365,          # single annual ship visit (Jan/Feb)
        resupply_window_open_doy=25,
    ),
}