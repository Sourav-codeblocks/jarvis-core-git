import type { OverlayPayload } from "./DataOverlay";

export const DEMO_LOW_STOCK: OverlayPayload = {
  type: "chart",
  label: "INVENTORY · LOW STOCK",
  freshness: "LIVE",
  content: {
    unit: "",
    data: [
      { label: "KP-001", value: 3, max: 50, tone: "red" },
      { label: "KP-014", value: 7, max: 50, tone: "red" },
      { label: "AX-220", value: 12, max: 50, tone: "amber" },
      { label: "AX-311", value: 18, max: 50, tone: "amber" },
      { label: "MV-044", value: 24, max: 50, tone: "amber" },
      { label: "MV-102", value: 31, max: 50, tone: "cyan" },
    ],
  },
};

export const DEMO_PENDING_ORDERS: OverlayPayload = {
  type: "table",
  label: "ORDERS · AWAITING APPROVAL",
  freshness: "LIVE",
  content: {
    columns: ["ORDER", "CUSTOMER", "AMOUNT", "AGED"],
    rows: [
      { id: "1", status: "urgent", cells: ["#8842", "M. Okafor", "$4,120.00", "3d 04h"] },
      { id: "2", status: "urgent", cells: ["#8839", "R. Delaney", "$980.50", "2d 11h"] },
      { id: "3", status: "pending", cells: ["#8851", "S. Iyer", "$1,240.00", "1d 02h"] },
      { id: "4", status: "pending", cells: ["#8855", "L. Weiss", "$612.00", "18h"] },
      { id: "5", status: "pending", cells: ["#8860", "H. Tanaka", "$3,400.00", "06h"] },
      { id: "6", status: "fulfilled", cells: ["#8834", "V. Ortega", "$210.00", "cleared"] },
    ],
  },
};

export const DEMO_FULFILLMENT_GAUGE: OverlayPayload = {
  type: "gauge",
  label: "FULFILLMENT RATE · 7D",
  freshness: "LIVE",
  content: { value: 87, tone: "green", sublabel: "ORDERS SHIPPED ON TIME", unit: "%" },
};

export const DEMO_ORDERS_WEEK: OverlayPayload = {
  type: "timeseries",
  label: "ORDERS · LAST 7 DAYS",
  freshness: "LIVE",
  content: {
    unit: "ORDERS",
    data: [
      { label: "MON", value: 24 },
      { label: "TUE", value: 31 },
      { label: "WED", value: 28 },
      { label: "THU", value: 42 },
      { label: "FRI", value: 55 },
      { label: "SAT", value: 47 },
      { label: "SUN", value: 38 },
    ],
  },
};

export const DEMOS: { label: string; payload: OverlayPayload }[] = [
  { label: "LOW STOCK", payload: DEMO_LOW_STOCK },
  { label: "PENDING ORDERS", payload: DEMO_PENDING_ORDERS },
  { label: "FULFILLMENT %", payload: DEMO_FULFILLMENT_GAUGE },
  { label: "ORDERS 7D", payload: DEMO_ORDERS_WEEK },
];
