import { createTheme } from "@mui/material/styles";

// Obserra brand tokens (extracted from provided assets)
const palette = {
  primary: { main: "#0B4F6C", contrastText: "#fff" },
  secondary: { main: "#FFA500", contrastText: "#000" },
  info: { main: "#4A90E2" },
  success: { main: "#34A853" },
  warning: { main: "#F6C358" },
  background: { default: "#F7FAFC", paper: "#fff" },
};

const theme = createTheme({
  palette: {
    mode: "light",
    ...palette,
  },
  typography: {
    fontFamily: ['Inter', 'Roboto', 'Helvetica', 'Arial', 'sans-serif'].join(","),
  },
});

export default theme;
