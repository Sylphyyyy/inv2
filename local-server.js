import "dotenv/config";
import { app } from "./src/server.js";

const port = Number(process.env.PORT || 3000);

app.listen(port, () => {
  console.log(`Procurement pipeline listening on port ${port}`);
});
