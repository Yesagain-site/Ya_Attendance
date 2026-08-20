import React, { useEffect, useState } from "react";
import {
  Card, Tabs, Form, InputNumber, Select, Button, message, Row, Col, Descriptions, Tag,
  Checkbox, Spin,
} from "antd";
import { api } from "../../api.js";
import { useAuth } from "../../auth.jsx";

const DAYS = [
  { label: "Monday", value: 0 }, { label: "Tuesday", value: 1 },
  { label: "Wednesday", value: 2 }, { label: "Thursday", value: 3 },
  { label: "Friday", value: 4 }, { label: "Saturday", value: 5 },
  { label: "Sunday", value: 6 },
];
const AS = [
  { value: "present", label: "Present" },
  { value: "absent", label: "Absent" },
  { value: "halfday", label: "Half day" },
];

// A tab section: local form seeded from shared rules, saves a merged rules object.
function Section({ rules, setRules, fields, children }) {
  const { isAdmin } = useAuth();
  const [form] = Form.useForm();
  const [saving, setSaving] = useState(false);
  useEffect(() => { form.setFieldsValue(rules); }, [rules]); // eslint-disable-line

  const save = async () => {
    const v = await form.validateFields(fields);
    setSaving(true);
    try {
      const merged = await api.saveRules({ ...rules, ...v });
      setRules(merged);
      message.success("Saved");
    } catch (e) { message.error(e.message); }
    finally { setSaving(false); }
  };

  return (
    <Form form={form} layout="vertical" disabled={!isAdmin}>
      {children}
      {isAdmin && <Button type="primary" onClick={save} loading={saving}>Save</Button>}
    </Form>
  );
}

function Calculation({ rules, setRules }) {
  return (
    <Section rules={rules} setRules={setRules}
      fields={["late_exceeds_min", "late_consider_as", "early_exceeds_min",
        "early_consider_as", "halfday_under_min", "missed_checkin_as", "missed_checkout_as"]}>
      <Card type="inner" title="Calculation Rule" style={{ marginBottom: 16 }}>
        <Row gutter={24}>
          <Col span={12}><Form.Item name="late_exceeds_min" label="When late exceeds (minutes) consider as">
            <InputNumber min={0} style={{ width: "100%" }} addonAfter={
              <Form.Item name="late_consider_as" noStyle><Select options={AS} style={{ width: 110 }} /></Form.Item>} />
          </Form.Item></Col>
          <Col span={12}><Form.Item name="early_exceeds_min" label="When early-leave exceeds (minutes) consider as">
            <InputNumber min={0} style={{ width: "100%" }} addonAfter={
              <Form.Item name="early_consider_as" noStyle><Select options={AS} style={{ width: 110 }} /></Form.Item>} />
          </Form.Item></Col>
          <Col span={12}><Form.Item name="halfday_under_min" label="When work duration is less than (minutes) → half day">
            <InputNumber min={0} style={{ width: "100%" }} /></Form.Item></Col>
          <Col span={6}><Form.Item name="missed_checkin_as" label="Missed Check-In as"><Select options={AS} /></Form.Item></Col>
          <Col span={6}><Form.Item name="missed_checkout_as" label="Missed Check-Out as"><Select options={AS} /></Form.Item></Col>
        </Row>
      </Card>
      <Card type="inner" title="Calculation Item (punch state mapping)" style={{ marginBottom: 16 }}>
        <Descriptions size="small" column={3} bordered>
          <Descriptions.Item label="Check In"><Tag>0</Tag></Descriptions.Item>
          <Descriptions.Item label="Check Out"><Tag>1</Tag></Descriptions.Item>
          <Descriptions.Item label="Break (Out)"><Tag>2</Tag></Descriptions.Item>
          <Descriptions.Item label="Break (In)"><Tag>3</Tag></Descriptions.Item>
          <Descriptions.Item label="Overtime In"><Tag>4</Tag></Descriptions.Item>
          <Descriptions.Item label="Overtime Out"><Tag>5</Tag></Descriptions.Item>
        </Descriptions>
      </Card>
    </Section>
  );
}

function Basic({ rules, setRules }) {
  return (
    <Section rules={rules} setRules={setRules}
      fields={["period_start_day", "first_weekday", "min_present_min"]}>
      <Card type="inner" title="Basic Settings" style={{ marginBottom: 16 }}>
        <Row gutter={24}>
          <Col span={8}><Form.Item name="period_start_day"
            label="Attendance month starts on day" tooltip="Payroll cycle start day (1–28)">
            <InputNumber min={1} max={28} style={{ width: "100%" }} /></Form.Item></Col>
          <Col span={8}><Form.Item name="first_weekday" label="First day of week">
            <Select options={[{ value: 0, label: "Monday" }, { value: 6, label: "Sunday" },
              { value: 5, label: "Saturday" }]} /></Form.Item></Col>
          <Col span={8}><Form.Item name="min_present_min"
            label="Minimum minutes to count as Present" tooltip="Below this, the day isn't counted as present">
            <InputNumber min={0} style={{ width: "100%" }} /></Form.Item></Col>
        </Row>
      </Card>
    </Section>
  );
}

function WeekOff({ rules, setRules }) {
  return (
    <Section rules={rules} setRules={setRules} fields={["week_off"]}>
      <Card type="inner" title="Week Off Settings" style={{ marginBottom: 16 }}>
        <p style={{ color: "#999", marginTop: 0 }}>
          Days selected here are weekly days off by default. A shift assigned to a department/employee
          overrides this for those people.
        </p>
        <Form.Item name="week_off">
          <Checkbox.Group options={DAYS} />
        </Form.Item>
      </Card>
    </Section>
  );
}

function Overtime({ rules, setRules }) {
  return (
    <Section rules={rules} setRules={setRules}
      fields={["ot_return_gap_min", "min_ot_min", "ot_multiplier"]}>
      <Card type="inner" title="Overtime Settings" style={{ marginBottom: 16 }}>
        <p style={{ color: "#999", marginTop: 0 }}>
          Overtime is a separate session after a shift's end time. Enable/disable OT per timetable.
        </p>
        <Row gutter={24}>
          <Col span={8}><Form.Item name="ot_return_gap_min"
            label="OT return gap (minutes)" tooltip="A gap this long after shift end marks an overtime return">
            <InputNumber min={1} style={{ width: "100%" }} /></Form.Item></Col>
          <Col span={8}><Form.Item name="min_ot_min"
            label="Minimum overtime (minutes)" tooltip="Ignore overtime shorter than this">
            <InputNumber min={0} style={{ width: "100%" }} /></Form.Item></Col>
          <Col span={8}><Form.Item name="ot_multiplier" label="OT rate (×)" tooltip="Informational">
            <InputNumber min={1} step={0.1} style={{ width: "100%" }} /></Form.Item></Col>
        </Row>
      </Card>
    </Section>
  );
}

export default function GlobalRule() {
  const [rules, setRules] = useState(null);
  useEffect(() => { api.rules().then(setRules).catch((e) => message.error(e.message)); }, []);
  if (!rules) return <Card title="Global Rule"><Spin /></Card>;

  const p = { rules, setRules };
  return (
    <Card title="Global Rule">
      <Tabs items={[
        { key: "basic", label: "Basic Settings", children: <Basic {...p} /> },
        { key: "weekoff", label: "Week Off Settings", children: <WeekOff {...p} /> },
        { key: "ot", label: "Overtime Settings", children: <Overtime {...p} /> },
        { key: "calc", label: "Calculation Settings", children: <Calculation {...p} /> },
      ]} />
    </Card>
  );
}
