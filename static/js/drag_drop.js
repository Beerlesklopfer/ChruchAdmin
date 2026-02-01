/**
 * Drag & Drop Funktionalität für Church Admin System
 * Verwendet SortableJS für intuitive Drag & Drop Operationen
 *
 * Unterstützt:
 * - Prozess-Schritte umsortieren
 * - Checklisten-Items neu ordnen
 * - Benutzer zu Gruppen zuweisen
 * - Familienmitglieder organisieren
 */

// ==================== PROZESS-SCHRITTE SORTIEREN ====================

function initProcessStepSorting() {
    const stepList = document.getElementById('process-steps-list');
    if (!stepList) return;

    new Sortable(stepList, {
        animation: 150,
        handle: '.drag-handle',
        ghostClass: 'sortable-ghost',
        dragClass: 'sortable-drag',
        onEnd: function(evt) {
            // Sammle neue Reihenfolge
            const steps = [];
            const stepElements = stepList.querySelectorAll('.process-step-item');

            stepElements.forEach((el, index) => {
                steps.push({
                    id: el.dataset.stepId,
                    order: index + 1
                });
            });

            // Sende Aktualisierung an Server
            updateProcessStepOrder(steps);
        }
    });
}

async function updateProcessStepOrder(steps) {
    try {
        const response = await fetch('/ldap/process/steps/reorder/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCsrfToken()
            },
            body: JSON.stringify({ steps: steps })
        });

        if (response.ok) {
            showToast('Reihenfolge aktualisiert', 'success');
        } else {
            showToast('Fehler beim Aktualisieren', 'error');
        }
    } catch (error) {
        console.error('Error updating step order:', error);
        showToast('Verbindungsfehler', 'error');
    }
}

// ==================== CHECKLISTEN-ITEMS SORTIEREN ====================

function initChecklistSorting() {
    const checklistContainers = document.querySelectorAll('.checklist-items');

    checklistContainers.forEach(container => {
        new Sortable(container, {
            animation: 150,
            handle: '.checklist-drag-handle',
            ghostClass: 'sortable-ghost',
            onEnd: function(evt) {
                const items = [];
                const itemElements = container.querySelectorAll('.checklist-item');

                itemElements.forEach((el, index) => {
                    items.push({
                        id: el.dataset.itemId,
                        order: index + 1
                    });
                });

                updateChecklistOrder(items);
            }
        });
    });
}

async function updateChecklistOrder(items) {
    try {
        const response = await fetch('/ldap/process/checklist/reorder/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCsrfToken()
            },
            body: JSON.stringify({ items: items })
        });

        if (response.ok) {
            showToast('Checkliste aktualisiert', 'success');
        }
    } catch (error) {
        console.error('Error updating checklist:', error);
    }
}

// ==================== GRUPPEN-MITGLIEDER DRAG & DROP ====================

function initGroupMemberDragDrop() {
    // Verfügbare Benutzer (Quelle)
    const availableUsers = document.getElementById('available-users');
    if (availableUsers) {
        new Sortable(availableUsers, {
            group: {
                name: 'users',
                pull: 'clone',
                put: false
            },
            animation: 150,
            sort: false,
            ghostClass: 'sortable-ghost'
        });
    }

    // Gruppenmitglieder (Ziel)
    const groupMembers = document.getElementById('group-members');
    if (groupMembers) {
        new Sortable(groupMembers, {
            group: 'users',
            animation: 150,
            ghostClass: 'sortable-ghost',
            onAdd: function(evt) {
                const userId = evt.item.dataset.userId;
                const groupDn = groupMembers.dataset.groupDn;
                addUserToGroup(userId, groupDn);
            },
            onRemove: function(evt) {
                const userId = evt.item.dataset.userId;
                const groupDn = groupMembers.dataset.groupDn;
                removeUserFromGroup(userId, groupDn);
            }
        });
    }
}

async function addUserToGroup(userId, groupDn) {
    try {
        const response = await fetch('/ldap/groups/add-member/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCsrfToken()
            },
            body: JSON.stringify({
                user_id: userId,
                group_dn: groupDn
            })
        });

        if (response.ok) {
            showToast('Benutzer zur Gruppe hinzugefügt', 'success');
        } else {
            showToast('Fehler beim Hinzufügen', 'error');
            // Rückgängig machen
            location.reload();
        }
    } catch (error) {
        console.error('Error adding user to group:', error);
        showToast('Verbindungsfehler', 'error');
    }
}

async function removeUserFromGroup(userId, groupDn) {
    try {
        const response = await fetch('/ldap/groups/remove-member/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCsrfToken()
            },
            body: JSON.stringify({
                user_id: userId,
                group_dn: groupDn
            })
        });

        if (response.ok) {
            showToast('Benutzer aus Gruppe entfernt', 'success');
        }
    } catch (error) {
        console.error('Error removing user from group:', error);
    }
}

// ==================== FAMILIEN-BAUM DRAG & DROP ====================

function initFamilyTreeDragDrop() {
    const familyMembers = document.querySelectorAll('.family-member-draggable');

    familyMembers.forEach(member => {
        new Sortable(member, {
            group: 'family',
            animation: 150,
            ghostClass: 'sortable-ghost',
            onEnd: function(evt) {
                const memberId = evt.item.dataset.memberId;
                const newParentId = evt.to.dataset.parentId;

                updateFamilyRelationship(memberId, newParentId);
            }
        });
    });
}

async function updateFamilyRelationship(memberId, newParentId) {
    try {
        const response = await fetch('/ldap/users/update-parent/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCsrfToken()
            },
            body: JSON.stringify({
                member_id: memberId,
                new_parent_id: newParentId
            })
        });

        if (response.ok) {
            showToast('Verwandtschaftsbeziehung aktualisiert', 'success');
        } else {
            showToast('Fehler beim Aktualisieren der Beziehung', 'error');
            location.reload();
        }
    } catch (error) {
        console.error('Error updating family relationship:', error);
        showToast('Verbindungsfehler', 'error');
    }
}

// ==================== UTILITY FUNCTIONS ====================

function getCsrfToken() {
    const token = document.querySelector('[name=csrfmiddlewaretoken]');
    return token ? token.value : '';
}

function showToast(message, type = 'info') {
    // Erstelle Toast-Element
    const toastHtml = `
        <div class="toast align-items-center text-white bg-${type === 'success' ? 'success' : 'danger'} border-0" role="alert">
            <div class="d-flex">
                <div class="toast-body">
                    <i class="bi bi-${type === 'success' ? 'check-circle' : 'exclamation-triangle'} me-2"></i>
                    ${message}
                </div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
            </div>
        </div>
    `;

    // Finde oder erstelle Toast-Container
    let toastContainer = document.getElementById('toast-container');
    if (!toastContainer) {
        toastContainer = document.createElement('div');
        toastContainer.id = 'toast-container';
        toastContainer.className = 'toast-container position-fixed top-0 end-0 p-3';
        toastContainer.style.zIndex = '9999';
        document.body.appendChild(toastContainer);
    }

    // Füge Toast hinzu
    const toastElement = document.createElement('div');
    toastElement.innerHTML = toastHtml;
    toastContainer.appendChild(toastElement.firstElementChild);

    // Initialisiere und zeige Toast
    const toast = new bootstrap.Toast(toastElement.firstElementChild);
    toast.show();

    // Entferne Toast nach dem Ausblenden
    toastElement.firstElementChild.addEventListener('hidden.bs.toast', function() {
        toastElement.remove();
    });
}

// ==================== INITIALIZATION ====================

document.addEventListener('DOMContentLoaded', function() {
    // Prüfe ob SortableJS verfügbar ist
    if (typeof Sortable === 'undefined') {
        console.warn('SortableJS nicht geladen. Drag & Drop deaktiviert.');
        return;
    }

    // Initialisiere alle Drag & Drop Funktionen
    initProcessStepSorting();
    initChecklistSorting();
    initGroupMemberDragDrop();
    initFamilyTreeDragDrop();

    console.log('Drag & Drop initialisiert');
});

// ==================== EXPORT FÜR EXTERNE VERWENDUNG ====================

window.ChurchAdmin = window.ChurchAdmin || {};
window.ChurchAdmin.DragDrop = {
    initProcessStepSorting,
    initChecklistSorting,
    initGroupMemberDragDrop,
    initFamilyTreeDragDrop,
    showToast
};
