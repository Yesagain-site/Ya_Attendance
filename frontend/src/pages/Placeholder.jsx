import React from "react";
import { Card, Empty } from "antd";

export default function Placeholder({ title, note }) {
  return (
    <Card title={title}>
      <Empty description={note || "Coming soon"} />
    </Card>
  );
}
