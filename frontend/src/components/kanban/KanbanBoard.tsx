import {
  DndContext,
  DragOverlay,
  PointerSensor,
  closestCorners,
  useDroppable,
  useSensor,
  useSensors,
  type DragEndEvent,
  type DragOverEvent,
  type DragStartEvent,
} from "@dnd-kit/core";
import { SortableContext, useSortable, verticalListSortingStrategy } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { useMemo, useState, type ReactNode } from "react";
import { cn } from "@/lib/utils";

export type KanbanItem = {
  id: string;
  columnId: string;
  title: string;
  subtitle?: string;
};

type ColumnDef = {
  id: string;
  label: string;
  badge?: ReactNode;
};

type Props = {
  columns: ColumnDef[];
  items: KanbanItem[];
  canDrop?: (item: KanbanItem, toColumnId: string) => boolean;
  onMove: (itemId: string, toColumnId: string) => void;
  renderCard?: (item: KanbanItem) => ReactNode;
};

function SortableCard({
  item,
  children,
}: {
  item: KanbanItem;
  children: ReactNode;
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({
    id: item.id,
    data: { type: "card", item },
  });
  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
  };
  return (
    <div
      ref={setNodeRef}
      style={style}
      className={cn(
        "cursor-grab rounded-[20px] border border-line bg-cream-100 p-4 shadow-[var(--shadow-1)] active:cursor-grabbing",
        "transition-transform duration-[280ms] ease-soft",
        isDragging && "opacity-40",
      )}
      {...attributes}
      {...listeners}
    >
      {children}
    </div>
  );
}

function ColumnDrop({
  column,
  items,
  accept,
  children,
}: {
  column: ColumnDef;
  items: KanbanItem[];
  accept: boolean;
  children: ReactNode;
}) {
  const { setNodeRef, isOver } = useDroppable({
    id: column.id,
    data: { type: "column", columnId: column.id },
  });
  return (
    <div
      ref={setNodeRef}
      className={cn(
        "min-w-[240px] max-w-[280px] flex-1 rounded-[24px] border p-3 transition-colors duration-[160ms]",
        accept || isOver ? "border-sage-500/50 bg-sage-500/5" : "border-line bg-warm-white/60",
      )}
    >
      <div className="mb-3 flex items-center justify-between px-1">
        {column.badge || <span className="label-caps text-text-muted">{column.label}</span>}
        <span className="text-xs text-text-muted">{items.length}</span>
      </div>
      <SortableContext items={items.map((i) => i.id)} strategy={verticalListSortingStrategy}>
        <div className="min-h-[120px] space-y-2">{children}</div>
      </SortableContext>
    </div>
  );
}

export function KanbanBoard({ columns, items, canDrop, onMove, renderCard }: Props) {
  const [activeId, setActiveId] = useState<string | null>(null);
  const [overColumn, setOverColumn] = useState<string | null>(null);

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
  );

  const byColumn = useMemo(() => {
    const map: Record<string, KanbanItem[]> = {};
    for (const col of columns) map[col.id] = [];
    for (const item of items) {
      if (!map[item.columnId]) map[item.columnId] = [];
      map[item.columnId].push(item);
    }
    return map;
  }, [columns, items]);

  const activeItem = items.find((i) => i.id === activeId) || null;

  function findColumnOf(id: string): string | null {
    if (columns.some((c) => c.id === id)) return id;
    const asItem = items.find((i) => i.id === id);
    return asItem?.columnId ?? null;
  }

  function onDragStart(event: DragStartEvent) {
    setActiveId(String(event.active.id));
  }

  function onDragOver(event: DragOverEvent) {
    const overId = event.over?.id ? String(event.over.id) : null;
    if (!overId || !activeItem) {
      setOverColumn(null);
      return;
    }
    setOverColumn(findColumnOf(overId));
  }

  function onDragEnd(event: DragEndEvent) {
    const overId = event.over?.id ? String(event.over.id) : null;
    const itemId = String(event.active.id);
    setActiveId(null);
    setOverColumn(null);
    if (!overId) return;
    const toColumn = findColumnOf(overId);
    if (!toColumn) return;
    const item = items.find((i) => i.id === itemId);
    if (!item || item.columnId === toColumn) return;
    if (canDrop && !canDrop(item, toColumn)) return;
    onMove(itemId, toColumn);
  }

  return (
    <DndContext
      sensors={sensors}
      collisionDetection={closestCorners}
      onDragStart={onDragStart}
      onDragOver={onDragOver}
      onDragEnd={onDragEnd}
    >
      <div className="flex gap-4 overflow-x-auto pb-4">
        {columns.map((col) => {
          const colItems = byColumn[col.id] || [];
          const accept =
            !!activeItem &&
            overColumn === col.id &&
            (!canDrop || canDrop(activeItem, col.id));
          return (
            <ColumnDrop key={col.id} column={col} items={colItems} accept={!!accept}>
              {colItems.map((item) => (
                <SortableCard key={item.id} item={item}>
                  {renderCard ? (
                    renderCard(item)
                  ) : (
                    <>
                      <p className="font-medium text-green-900">{item.title}</p>
                      {item.subtitle && (
                        <p className="mt-1 text-sm text-text-muted">{item.subtitle}</p>
                      )}
                    </>
                  )}
                </SortableCard>
              ))}
              {!colItems.length && (
                <p className="px-2 py-6 text-center text-sm text-text-soft">Vacío</p>
              )}
            </ColumnDrop>
          );
        })}
      </div>
      <DragOverlay>
        {activeItem ? (
          <div className="rounded-[20px] border border-green-900/20 bg-cream-100 p-4 shadow-lg">
            <p className="font-medium text-green-900">{activeItem.title}</p>
            {activeItem.subtitle && (
              <p className="mt-1 text-sm text-text-muted">{activeItem.subtitle}</p>
            )}
          </div>
        ) : null}
      </DragOverlay>
    </DndContext>
  );
}
