import React from "react";
import { Card, CardContent, Typography } from "@mui/material";

export default function KPI({ title, value }) {
  return (
    <Card sx={{ mb: 2 }}>
      <CardContent>
        <Typography variant="subtitle2">{title}</Typography>
        <Typography variant="h5">{value}</Typography>
      </CardContent>
    </Card>
  );
}
