import axios from "axios";
import { apiBaseUrl } from "./runtime";

const api = axios.create({
  baseURL: apiBaseUrl,
  headers: {
    "Content-Type": "application/json",
  },
});

export default api;
