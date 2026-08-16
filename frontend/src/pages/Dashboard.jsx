import React from "react";
import { Box, Grid, Container, Typography } from "@mui/material";
import HealthCard from "../components/health/HealthCard";
import KPI from "../components/health/KPI";

export default function Dashboard() {
  return (
    <Container maxWidth="xl" sx={{ mt: 3 }}>
      <Typography variant="h4" gutterBottom>Overview</Typography>
      <Grid container spacing={3}>
        <Grid item xs={12} md={8}>
          <HealthCard />
        </Grid>
        <Grid item xs={12} md={4}>
          <KPI title="Connected" value="-" />
          <KPI title="Orgs" value="-" />
        </Grid>
      </Grid>
    </Container>
  );
}
