import React from "react";
import { Table } from "antd";

/**
 * Standard data table: only the rows scroll (fixed-height body), the column
 * header stays put, and pagination/filters above stay visible — the page never
 * scrolls because of the table. ~100/200 rows per page.
 */
export default function DataGrid({ pagination, scroll, size = "middle", ...props }) {
  return (
    <Table
      size={size}
      scroll={{ y: "calc(100vh - 320px)", ...(scroll || {}) }}
      pagination={
        pagination === false
          ? false
          : {
              defaultPageSize: 100,
              showSizeChanger: true,
              pageSizeOptions: ["50", "100", "200"],
              ...(pagination || {}),
            }
      }
      {...props}
    />
  );
}
