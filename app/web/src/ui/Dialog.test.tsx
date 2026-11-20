// Pencere (ui/Dialog): Esc bütün pencereleri kapatır (K-187). Odak pencerenin içindeyken de dışındayken de (ör. boş alana tıklandıktan sonra);
// üst üste pencerede yalnız en üstteki; atlanamaz pencere kapanmaz; açık açılır öğe (takvim, aramalı liste, menü) varken önce o kapanır.
import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { ConfirmDialog, Dialog } from "./Dialog";
import { TextField } from "./fields";

function Sample({ onClose, dismissible = true, title = "Pencere" }: { onClose(): void; dismissible?: boolean; title?: string }) {
  return (
    <Dialog title={title} onClose={onClose} onSubmit={() => undefined} submitLabel="Kaydet" dismissible={dismissible}>
      <TextField label="Ad" value="" onChange={() => undefined} />
    </Dialog>
  );
}

describe("pencere · Esc (K-187)", () => {
  it("odak içerideyken ve dışarıdayken kapatır", async () => {
    const user = userEvent.setup();
    const close = vi.fn();
    render(<Sample onClose={close} />);
    expect(screen.getByRole("textbox", { name: "Ad" })).toHaveFocus();                    // açılınca ilk alan seçili
    await user.keyboard("{Escape}");
    expect(close).toHaveBeenCalledTimes(1);
    (document.activeElement as HTMLElement).blur();                                       // boş alana tıklanmış gibi: odak pencerede değil
    expect(document.body).toHaveFocus();
    fireEvent.keyDown(document.body, { key: "Escape" });
    expect(close).toHaveBeenCalledTimes(2);
  });

  it("atlanamaz pencere kapanmaz; üst üste pencerede yalnız en üstteki kapanır; onay penceresi de kapanır", () => {
    const [locked, lower, upper, cancel] = [vi.fn(), vi.fn(), vi.fn(), vi.fn()];
    const first = render(<Sample onClose={locked} dismissible={false} />);
    fireEvent.keyDown(document.body, { key: "Escape" });
    expect(locked).not.toHaveBeenCalled();
    first.unmount();
    const both = render(<><Sample onClose={lower} title="Alt" /><Sample onClose={upper} title="Üst" /></>);
    (document.activeElement as HTMLElement).blur();
    fireEvent.keyDown(document.body, { key: "Escape" });
    expect(upper).toHaveBeenCalledTimes(1);
    expect(lower).not.toHaveBeenCalled();
    both.unmount();
    render(<ConfirmDialog title="Silinsin mi?" message="x" confirmLabel="Sil" onConfirm={() => undefined} onCancel={cancel} />);
    (document.activeElement as HTMLElement).blur();
    fireEvent.keyDown(document.body, { key: "Escape" });
    expect(cancel).toHaveBeenCalledTimes(1);
  });

  it("açık açılır öğe varken pencere kapanmaz (önce o kapanır)", () => {
    const close = vi.fn();
    render(<><Sample onClose={close} /><div className="sc-floating">liste</div></>);
    (document.activeElement as HTMLElement).blur();
    fireEvent.keyDown(document.body, { key: "Escape" });
    expect(close).not.toHaveBeenCalled();
  });
});
