import React from "react";
import { Card, CardContent, Typography, Grid, CircularProgress } from "@mui/material";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

async function fetchHealth() {
  const r = await api.get("/health");
  return r.data;
}

export default function HealthCard() {
  const { data, isLoading, error } = useQuery(["health"], fetchHealth, { refetchInterval: 20000 });

  if (isLoading) return <CircularProgress />;
  if (error) return <div>Error loading health</div>;

  return (
    <Card>
      <CardContent>
        <Typography variant="h6">System Health</Typography>
        <Grid container spacing={2} sx={{ mt: 1 }}>
          <Grid item xs={6} md={3}>
            <Typography variant="subtitle2">Status</Typography>
            <Typography>{data.status}</Typography>
          </Grid>
          <Grid item xs={6} md={3}>
            <Typography variant="subtitle2">DB OK</Typography>
            <Typography>{data.db ? "Yes" : "No"}</Typography>
          </Grid>
          <Grid item xs={6} md={3}>
            <Typography variant="subtitle2">Connectors</Typography>
            <Typography>{(data.checks?.connectors?.connected || 0) + "/" + (data.checks?.connectors?.total || 0)}</Typography>
          </Grid>
          <Grid item xs={6} md={3}>
            <Typography variant="subtitle2">Orgs</Typography>
            <Typography>{data.checks?.organizations ?? "-"}</Typography>
          </Grid>
        </Grid>
      </CardContent>
    </Card>
  );
}
