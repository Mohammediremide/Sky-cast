const form = document.getElementById("search-form");
const countrySelect = document.getElementById("country-select");
const stateSelect = document.getElementById("state-select");
const citySelect = document.getElementById("city-select");
const locationBtn = document.getElementById("location-btn");
const statusEl = document.getElementById("status");

const weatherCard = document.getElementById("weather-card");
const forecastWrap = document.getElementById("forecast-wrap");
const forecastEl = document.getElementById("forecast");

const cityNameEl = document.getElementById("city-name");
const timestampEl = document.getElementById("timestamp");
const tempEl = document.getElementById("temp");
const conditionEl = document.getElementById("condition");
const feelsLikeEl = document.getElementById("feels-like");
const windEl = document.getElementById("wind");
const humidityEl = document.getElementById("humidity");

const DEG = String.fromCharCode(176);

function setStatus(message, type = "") {
  statusEl.textContent = message;
  statusEl.className = `status ${type}`.trim();
}

function setLoading(loading) {
  const controls = [form.querySelector("button"), locationBtn, countrySelect, stateSelect, citySelect];
  controls.forEach((control) => {
    control.disabled = loading;
  });
}

async function getJSON(url) {
  const res = await fetch(url, { cache: "no-store" });
  let data;

  try {
    data = await res.json();
  } catch {
    throw new Error("Unexpected response from server.");
  }

  if (!res.ok) {
    throw new Error(data.error || "Failed to fetch data.");
  }

  return data;
}

function resetCities() {
  citySelect.innerHTML = '<option value="">Select city</option>';
  citySelect.disabled = true;
  citySelect.classList.add("hidden");
}

function resetStates() {
  stateSelect.innerHTML = '<option value="">Select state</option>';
  stateSelect.disabled = true;
  resetCities();
}

async function loadStatesForCountry() {
  const selectedOption = countrySelect.options[countrySelect.selectedIndex];
  const countryName = selectedOption ? selectedOption.textContent : "";

  resetStates();

  if (!countryName) {
    setStatus("Select a country to load states.");
    return;
  }

  setStatus("Loading states...");

  try {
    const payload = await getJSON(`/api/states?country_name=${encodeURIComponent(countryName)}`);
    const states = payload.states || [];

    if (!states.length) {
      setStatus("No states found for this country.", "error");
      return;
    }

    const fragment = document.createDocumentFragment();
    states.forEach((name) => {
      const option = document.createElement("option");
      option.value = name;
      option.textContent = name;
      fragment.appendChild(option);
    });

    stateSelect.appendChild(fragment);
    stateSelect.disabled = false;
    setStatus("Select a state to load cities.");
  } catch {
    setStatus("Could not load states for this country.", "error");
  }
}

async function loadCitiesForState() {
  const countryName = countrySelect.options[countrySelect.selectedIndex]?.textContent?.trim() || "";
  const stateName = stateSelect.value.trim();

  resetCities();

  if (!stateName) {
    setStatus("Select a state to load cities.");
    return;
  }

  setStatus("Loading cities...");

  try {
    const payload = await getJSON(
      `/api/cities?country_name=${encodeURIComponent(countryName)}&state=${encodeURIComponent(stateName)}`
    );
    const cities = payload.cities || [];

    if (!cities.length) {
      setStatus("No cities found for this state.", "error");
      return;
    }

    const fragment = document.createDocumentFragment();
    cities.forEach((name) => {
      const option = document.createElement("option");
      option.value = name;
      option.textContent = name;
      fragment.appendChild(option);
    });

    citySelect.appendChild(fragment);
    citySelect.disabled = false;
    citySelect.classList.remove("hidden");
    setStatus("Select a city, then search.");
  } catch (error) {
    setStatus(error.message || "Could not load cities for this state.", "error");
  }
}

async function loadCountries() {
  try {
    const payload = await getJSON("/api/countries");
    const countries = payload.countries || [];

    if (!countries.length) {
      setStatus("Could not load countries.", "error");
      return;
    }

    const fragment = document.createDocumentFragment();
    countries.forEach((country) => {
      const option = document.createElement("option");
      option.value = country.code;
      option.textContent = country.name;
      fragment.appendChild(option);
    });

    countrySelect.appendChild(fragment);
    setStatus("Select a country to load states.");
  } catch {
    setStatus("Could not load countries.", "error");
  }
}

function renderCurrent(payload) {
  const location = payload.location;
  const current = payload.current;

  cityNameEl.textContent = [location.name, location.country_name].filter(Boolean).join(", ");
  timestampEl.textContent = `Updated ${new Date(current.timestamp * 1000).toLocaleString()}`;
  tempEl.textContent = `${current.temp}${DEG}C`;
  conditionEl.textContent = current.condition;
  feelsLikeEl.textContent = `${current.feels_like}${DEG}C`;
  windEl.textContent = `${current.wind_kmh} km/h`;
  humidityEl.textContent = `${current.humidity}%`;

  weatherCard.classList.remove("hidden");
}

function renderForecast(payload) {
  forecastEl.innerHTML = "";

  payload.forecast.forEach((day) => {
    const card = document.createElement("article");
    card.className = "forecast-day";

    const dayLabel = new Date(day.date).toLocaleDateString(undefined, {
      weekday: "short",
      month: "short",
      day: "numeric"
    });

    card.innerHTML = `
      <p><strong>${dayLabel}</strong></p>
      <p>${day.condition}</p>
      <p>High: ${day.temp_max}${DEG}C</p>
      <p>Low: ${day.temp_min}${DEG}C</p>
    `;

    forecastEl.appendChild(card);
  });

  forecastWrap.classList.remove("hidden");
}

async function loadWeather(url) {
  setLoading(true);
  setStatus("Fetching live weather...");

  try {
    const payload = await getJSON(url);
    renderCurrent(payload);
    renderForecast(payload);

    if (payload.forecast.length < 5) {
      setStatus(`Weather updated. Provider returned ${payload.forecast.length} day(s) on your plan.`, "success");
    } else {
      setStatus("Weather updated successfully.", "success");
    }
  } catch (error) {
    setStatus(error.message || "Failed to load weather.", "error");
  } finally {
    setLoading(false);
  }
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();

  const countryCode = countrySelect.value.trim();
  const countryName = countrySelect.options[countrySelect.selectedIndex]?.textContent?.trim() || "";
  const state = stateSelect.value.trim();
  const city = citySelect.value.trim();

  if (!countryCode) {
    setStatus("Select a country.", "error");
    return;
  }

  if (!state) {
    setStatus("Select a state.", "error");
    return;
  }

  if (!city) {
    setStatus("Select a city.", "error");
    return;
  }

  const query = new URLSearchParams({ city, state, country: countryCode, country_name: countryName });
  await loadWeather(`/api/weather?${query.toString()}`);
});

countrySelect.addEventListener("change", loadStatesForCountry);
stateSelect.addEventListener("change", loadCitiesForState);

locationBtn.addEventListener("click", () => {
  if (!navigator.geolocation) {
    setStatus("Geolocation is not supported in this browser.", "error");
    return;
  }

  setStatus("Getting your location...");
  setLoading(true);

  navigator.geolocation.getCurrentPosition(
    async (pos) => {
      const { latitude, longitude } = pos.coords;
      await loadWeather(`/api/weather/coords?lat=${latitude}&lon=${longitude}`);
    },
    (err) => {
      setStatus(`Location access failed: ${err.message}`, "error");
      setLoading(false);
    },
    { enableHighAccuracy: true, timeout: 10000 }
  );
});

resetStates();
loadCountries();
