import React from "react";
import { Avatar, Popover } from "antd";
import { UserOutlined } from "@ant-design/icons";
import { photoUrl } from "../api.js";

/**
 * Small avatar that, on hover, pops a large (3x) photo for better visibility.
 * Falls back to `children` (e.g. an initial) or a user icon when no photo.
 */
export default function PhotoAvatar({ pin, hasPhoto, name, size = "small", style, children }) {
  const src = hasPhoto ? photoUrl(pin) : undefined;
  const avatar = (
    <Avatar size={size} src={src} style={{ cursor: hasPhoto ? "zoom-in" : "default", ...style }}
      icon={!children ? <UserOutlined /> : undefined}>
      {children}
    </Avatar>
  );
  if (!hasPhoto) return avatar;
  return (
    <Popover trigger="hover" mouseEnterDelay={0.15} title={name || pin} placement="right"
      content={<img src={src} alt={name || pin}
        style={{ width: 150, height: 150, objectFit: "cover", borderRadius: 8, display: "block" }} />}>
      {avatar}
    </Popover>
  );
}
