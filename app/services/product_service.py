from typing import List, Optional, Tuple, Dict
from app.db.database import db_helper
from app.models.product import ProductCreate, ProductUpdate
import aiosqlite
import json
import uuid


class ProductService:

    # ------------------------------------------------------------------ #
    #  Internal Helpers                                                     #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _process_product_row(row: dict) -> dict:
        data = dict(row)
        if data.get("images"):
            try:
                data["images"] = json.loads(data["images"])
            except Exception:
                data["images"] = []
        else:
            data["images"] = []
        return data

    @staticmethod
    async def _get_variant_types_for_product(db: aiosqlite.Connection, product_id: str) -> List[dict]:
        """Return variant types with their option value lists for a product."""
        async with db.execute(
            "SELECT id, name, display_order FROM variant_types WHERE product_id = ? ORDER BY display_order, name",
            (product_id,)
        ) as cursor:
            type_rows = await cursor.fetchall()

        result = []
        for vt in type_rows:
            vt_id = vt[0]
            async with db.execute(
                "SELECT value FROM variant_options WHERE variant_type_id = ? ORDER BY display_order, value",
                (vt_id,)
            ) as opt_cursor:
                options = [r[0] for r in await opt_cursor.fetchall()]
            result.append({
                "id": vt_id,
                "product_id": product_id,
                "name": vt[1],
                "display_order": vt[2],
                "options": options,
            })
        return result

    @staticmethod
    async def _get_variants_for_product(db: aiosqlite.Connection, product_id: str) -> List[dict]:
        """Return concrete variants with dynamic attributes map."""
        async with db.execute("""
            SELECT pv.id, pv.product_id, pv.sku, pv.price, pv.created_at, pv.updated_at, pv.images,
                   COALESCE(i.quantity, 0) as stock,
                   COALESCE((
                       SELECT SUM(r.quantity)
                       FROM reservations r
                       WHERE r.variant_id = pv.id AND r.status = 'RESERVED'
                   ), 0) as reserved
            FROM product_variants pv
            LEFT JOIN inventory i ON pv.id = i.variant_id
            WHERE pv.product_id = ?
        """, (product_id,)) as cursor:
            rows = await cursor.fetchall()

        results = []
        for row in rows:
            images_raw = row[6]
            v_images = []
            if images_raw:
                try:
                    v_images = json.loads(images_raw)
                except Exception:
                    v_images = []

            variant = {
                "id": row[0],
                "product_id": row[1],
                "sku": row[2],
                "price": row[3],
                "created_at": row[4],
                "updated_at": row[5],
                "images": v_images,
                "stock": row[7],
                "reserved": row[8],
                "attributes": {},
            }

            # Build attributes map: { TypeName: OptionValue }
            async with db.execute("""
                SELECT vt.name, vo.value
                FROM variant_option_assignments voa
                JOIN variant_options vo ON voa.variant_option_id = vo.id
                JOIN variant_types vt ON vo.variant_type_id = vt.id
                WHERE voa.variant_id = ?
                ORDER BY vt.display_order, vt.name
            """, (row[0],)) as attr_cursor:
                for attr_row in await attr_cursor.fetchall():
                    variant["attributes"][attr_row[0]] = attr_row[1]

            results.append(variant)
        return results

    # ------------------------------------------------------------------ #
    #  Variant Type / Option helpers                                        #
    # ------------------------------------------------------------------ #

    @staticmethod
    async def _upsert_variant_types(db: aiosqlite.Connection, product_id: str, variant_types: list) -> Dict[str, Dict[str, str]]:
        """
        Upsert variant types + options. Returns a lookup map:
            { type_name: { option_value: option_id } }
        """
        type_option_map: Dict[str, Dict[str, str]] = {}

        for vt in variant_types:
            type_name = vt.name if hasattr(vt, "name") else vt["name"]
            options = vt.options if hasattr(vt, "options") else vt["options"]
            display_order = vt.display_order if hasattr(vt, "display_order") else vt.get("display_order", 0)

            # Upsert variant_type
            async with db.execute(
                "SELECT id FROM variant_types WHERE product_id = ? AND name = ?",
                (product_id, type_name)
            ) as cursor:
                existing_type = await cursor.fetchone()

            if existing_type:
                vt_id = existing_type[0]
            else:
                vt_id = str(uuid.uuid4())
                await db.execute(
                    "INSERT INTO variant_types (id, product_id, name, display_order) VALUES (?, ?, ?, ?)",
                    (vt_id, product_id, type_name, display_order)
                )

            type_option_map[type_name] = {}

            # Upsert each option
            for idx, opt_val in enumerate(options):
                async with db.execute(
                    "SELECT id FROM variant_options WHERE variant_type_id = ? AND value = ?",
                    (vt_id, opt_val)
                ) as cursor:
                    existing_opt = await cursor.fetchone()

                if existing_opt:
                    opt_id = existing_opt[0]
                else:
                    opt_id = str(uuid.uuid4())
                    await db.execute(
                        "INSERT INTO variant_options (id, variant_type_id, value, display_order) VALUES (?, ?, ?, ?)",
                        (opt_id, vt_id, opt_val, idx)
                    )

                type_option_map[type_name][opt_val] = opt_id

        return type_option_map

    @staticmethod
    async def _assign_variant_options(
        db: aiosqlite.Connection,
        variant_id: str,
        product_id: str,
        attributes: Dict[str, str]
    ):
        """Assign the option IDs to a concrete variant based on an attributes dict."""
        # Delete existing assignments first (for upsert)
        await db.execute(
            "DELETE FROM variant_option_assignments WHERE variant_id = ?",
            (variant_id,)
        )

        for type_name, option_value in attributes.items():
            # Resolve option_id
            async with db.execute("""
                SELECT vo.id FROM variant_options vo
                JOIN variant_types vt ON vo.variant_type_id = vt.id
                WHERE vt.product_id = ? AND vt.name = ? AND vo.value = ?
            """, (product_id, type_name, option_value)) as cursor:
                opt_row = await cursor.fetchone()

            if opt_row:
                await db.execute(
                    "INSERT OR IGNORE INTO variant_option_assignments (variant_id, variant_option_id) VALUES (?, ?)",
                    (variant_id, opt_row[0])
                )

    # ------------------------------------------------------------------ #
    #  CRUD                                                                #
    # ------------------------------------------------------------------ #

    @staticmethod
    async def get_products(limit: int = 10, offset: int = 0) -> Tuple[List[dict], int]:
        async with db_helper.get_db_connection() as db:
            async with db.execute("SELECT COUNT(*) FROM products") as cursor:
                total = (await cursor.fetchone())[0]

            async with db.execute("""
                SELECT p.*,
                       COALESCE((SELECT SUM(quantity) FROM inventory WHERE product_id = p.id), 0) as stock,
                       COALESCE((SELECT SUM(quantity) FROM reservations WHERE product_id = p.id AND status = 'RESERVED'), 0) as reserved
                FROM products p
                ORDER BY p.created_at DESC LIMIT ? OFFSET ?
            """, (limit, offset)) as cursor:
                rows = await cursor.fetchall()
                items = []
                for row in rows:
                    product = ProductService._process_product_row(row)
                    product["variant_types"] = await ProductService._get_variant_types_for_product(db, product["id"])
                    product["variants"] = await ProductService._get_variants_for_product(db, product["id"])
                    items.append(product)

            return items, total

    @staticmethod
    async def get_product_by_id(product_id: str) -> Optional[dict]:
        async with db_helper.get_db_connection() as db:
            async with db.execute("""
                SELECT p.*,
                       COALESCE((SELECT SUM(quantity) FROM inventory WHERE product_id = p.id), 0) as stock,
                       COALESCE((SELECT SUM(quantity) FROM reservations WHERE product_id = p.id AND status = 'RESERVED'), 0) as reserved
                FROM products p WHERE p.id = ?
            """, (product_id,)) as cursor:
                row = await cursor.fetchone()
                if not row:
                    return None
                product = ProductService._process_product_row(row)
                product["variant_types"] = await ProductService._get_variant_types_for_product(db, product_id)
                product["variants"] = await ProductService._get_variants_for_product(db, product_id)
                return product

    @staticmethod
    async def get_product_by_sku(sku: str) -> Optional[dict]:
        async with db_helper.get_db_connection() as db:
            async with db.execute("""
                SELECT p.*,
                       COALESCE((SELECT SUM(quantity) FROM inventory WHERE product_id = p.id), 0) as stock,
                       COALESCE((SELECT SUM(quantity) FROM reservations WHERE product_id = p.id AND status = 'RESERVED'), 0) as reserved
                FROM products p WHERE p.sku = ?
            """, (sku,)) as cursor:
                row = await cursor.fetchone()
                if not row:
                    return None
                product = ProductService._process_product_row(row)
                product_id = product["id"]
                product["variant_types"] = await ProductService._get_variant_types_for_product(db, product_id)
                product["variants"] = await ProductService._get_variants_for_product(db, product_id)
                return product

    @staticmethod
    async def create_product(product: ProductCreate) -> dict:
        # SKU idempotency check
        existing = await ProductService.get_product_by_sku(product.sku)
        if existing:
            return existing

        async with db_helper.get_db_connection() as db:
            await db.execute("BEGIN IMMEDIATE")
            try:
                product_id = str(uuid.uuid4())
                images_json = json.dumps(product.images) if product.images else None

                await db.execute(
                    "INSERT INTO products (id, name, sku, description, base_price, images) VALUES (?, ?, ?, ?, ?, ?)",
                    (product_id, product.name, product.sku, product.description, product.base_price, images_json)
                )

                # Upsert variant types + options first
                type_option_map: Dict[str, Dict[str, str]] = {}
                if product.variant_types:
                    type_option_map = await ProductService._upsert_variant_types(db, product_id, product.variant_types)

                # Create concrete variants
                if product.variants:
                    for variant in product.variants:
                        variant_id = str(uuid.uuid4())
                        v_images_json = json.dumps(variant.images) if variant.images else None
                        await db.execute(
                            "INSERT INTO product_variants (id, product_id, sku, price, images) VALUES (?, ?, ?, ?, ?)",
                            (variant_id, product_id, variant.sku, variant.price, v_images_json)
                        )

                        # Assign option attributes
                        if variant.attributes:
                            await ProductService._assign_variant_options(db, variant_id, product_id, variant.attributes)

                        # Initialize inventory
                        initial_qty = variant.initial_stock or 0
                        inv_id = str(uuid.uuid4())
                        await db.execute(
                            "INSERT INTO inventory (id, product_id, variant_id, quantity) VALUES (?, ?, ?, ?)",
                            (inv_id, product_id, variant_id, initial_qty)
                        )
                        if initial_qty > 0:
                            await db.execute(
                                "INSERT INTO stock_movements (id, product_id, variant_id, quantity, type, reference_id) VALUES (?, ?, ?, ?, 'IN', 'INITIAL_STOCK')",
                                (str(uuid.uuid4()), product_id, variant_id, initial_qty)
                            )

                await db.commit()
                return await ProductService.get_product_by_id(product_id)
            except Exception as e:
                await db.rollback()
                raise e

    @staticmethod
    async def update_product(product_id: str, product_update: ProductUpdate) -> Optional[dict]:
        async with db_helper.get_db_connection() as db:
            await db.execute("BEGIN IMMEDIATE")
            try:
                update_data = product_update.model_dump(exclude_unset=True)
                variant_types_data = update_data.pop("variant_types", None)
                variants_data = update_data.pop("variants", None)

                # Update product scalar fields
                if update_data:
                    if "images" in update_data:
                        update_data["images"] = json.dumps(update_data["images"])
                    fields = ", ".join([f"{k} = ?" for k in update_data.keys()])
                    values = list(update_data.values())
                    values.append(product_id)
                    await db.execute(
                        f"UPDATE products SET {fields}, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                        values
                    )

                # Upsert variant types/options
                type_option_map: Dict[str, Dict[str, str]] = {}
                if variant_types_data is not None:
                    type_option_map = await ProductService._upsert_variant_types(db, product_id, variant_types_data)

                # Update concrete variants
                if variants_data is not None:
                    async with db.execute(
                        "SELECT id FROM product_variants WHERE product_id = ?", (product_id,)
                    ) as cursor:
                        current_variant_ids = {row[0] for row in await cursor.fetchall()}

                    submitted_ids = {v["id"] for v in variants_data if v.get("id")}
                    ids_to_delete = current_variant_ids - submitted_ids
                    if ids_to_delete:
                        placeholders = ", ".join(["?"] * len(ids_to_delete))
                        await db.execute(
                            f"DELETE FROM product_variants WHERE id IN ({placeholders})",
                            list(ids_to_delete)
                        )

                    for variant in variants_data:
                        v_id = variant.get("id")
                        attributes = variant.get("attributes") or {}

                        if v_id and v_id in current_variant_ids:
                            # Update existing variant
                            update_fields = []
                            update_vals = []
                            if variant.get("sku"):
                                update_fields.append("sku = ?")
                                update_vals.append(variant["sku"])
                            if variant.get("price") is not None:
                                update_fields.append("price = ?")
                                update_vals.append(variant["price"])
                            if "images" in variant:
                                v_imgs = variant.get("images")
                                update_fields.append("images = ?")
                                update_vals.append(json.dumps(v_imgs) if v_imgs else None)

                            if update_fields:
                                update_vals.append(v_id)
                                await db.execute(
                                    f"UPDATE product_variants SET {', '.join(update_fields)}, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                                    update_vals
                                )

                            if attributes:
                                await ProductService._assign_variant_options(db, v_id, product_id, attributes)

                            # Handle stock update
                            stock_qty = variant.get("stock")
                            if stock_qty is not None:
                                async with db.execute(
                                    "SELECT quantity FROM inventory WHERE variant_id = ?", (v_id,)
                                ) as inv_cur:
                                    inv_row = await inv_cur.fetchone()
                                if inv_row is None:
                                    await db.execute(
                                        "INSERT INTO inventory (id, product_id, variant_id, quantity) VALUES (?, ?, ?, ?)",
                                        (str(uuid.uuid4()), product_id, v_id, stock_qty)
                                    )
                                    if stock_qty > 0:
                                        await db.execute(
                                            "INSERT INTO stock_movements (id, product_id, variant_id, quantity, type, reference_id) VALUES (?, ?, ?, ?, 'IN', 'INITIAL_STOCK')",
                                            (str(uuid.uuid4()), product_id, v_id, stock_qty)
                                        )
                                else:
                                    old_qty = inv_row[0]
                                    diff = stock_qty - old_qty
                                    if diff != 0:
                                        await db.execute(
                                            "UPDATE inventory SET quantity = ?, updated_at = CURRENT_TIMESTAMP WHERE variant_id = ?",
                                            (stock_qty, v_id)
                                        )
                                        move_type = "IN" if diff > 0 else "ADJUST"
                                        await db.execute(
                                            "INSERT INTO stock_movements (id, product_id, variant_id, quantity, type, reference_id) VALUES (?, ?, ?, ?, ?, 'VARIANT_UPDATE')",
                                            (str(uuid.uuid4()), product_id, v_id, abs(diff), move_type)
                                        )
                        else:
                            # Insert new variant
                            new_v_id = str(uuid.uuid4())
                            v_imgs = variant.get("images")
                            v_imgs_json = json.dumps(v_imgs) if v_imgs else None
                            await db.execute(
                                "INSERT INTO product_variants (id, product_id, sku, price, images) VALUES (?, ?, ?, ?, ?)",
                                (new_v_id, product_id, variant.get("sku"), variant.get("price", 0), v_imgs_json)
                            )
                            if attributes:
                                await ProductService._assign_variant_options(db, new_v_id, product_id, attributes)

                            initial_qty = variant.get("stock") or 0
                            await db.execute(
                                "INSERT INTO inventory (id, product_id, variant_id, quantity) VALUES (?, ?, ?, ?)",
                                (str(uuid.uuid4()), product_id, new_v_id, initial_qty)
                            )
                            if initial_qty > 0:
                                await db.execute(
                                    "INSERT INTO stock_movements (id, product_id, variant_id, quantity, type, reference_id) VALUES (?, ?, ?, ?, 'IN', 'INITIAL_STOCK')",
                                    (str(uuid.uuid4()), product_id, new_v_id, initial_qty)
                                )

                await db.commit()
                return await ProductService.get_product_by_id(product_id)
            except Exception as e:
                await db.rollback()
                raise e

    @staticmethod
    async def get_variant_types_for_product(product_id: str) -> List[dict]:
        async with db_helper.get_db_connection() as db:
            return await ProductService._get_variant_types_for_product(db, product_id)


product_service = ProductService()
